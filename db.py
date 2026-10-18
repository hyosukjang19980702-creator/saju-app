"""데이터 계층: 회원, 주문, 설정, 이벤트, 이메일 인증코드.

- DATABASE_URL 환경변수가 있으면 PostgreSQL(외부 DB, 앱이 재시작돼도 데이터 유지)
- 없으면 로컬 SQLite 파일(SAJU_DB, 기본 saju.db) — 내 컴퓨터 테스트용
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

KST = ZoneInfo("Asia/Seoul")
DEFAULT_ADMIN = ("admin@saju.local", "admin1234!")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_TTL_MIN = 10
CODE_COOLDOWN_SEC = 60
CODE_MAX_ATTEMPTS = 5

_engine = None


def _url() -> str:
    u = os.environ.get("DATABASE_URL", "").strip()
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://"):]
    if u.startswith("postgresql://"):
        u = "postgresql+psycopg2://" + u[len("postgresql://"):]
    return u or f"sqlite:///{os.environ.get('SAJU_DB', 'saju.db')}"


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(_url(), pool_pre_ping=True, pool_recycle=300)
    return _engine


def is_pg() -> bool:
    return engine().dialect.name == "postgresql"


def now() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)


# ---------- 쿼리 헬퍼 ----------
def execute(sql: str, **p):
    with engine().begin() as c:
        c.execute(text(sql), p)


def insert_returning_id(sql: str, **p) -> int:
    with engine().begin() as c:
        return c.execute(text(sql + " RETURNING id"), p).scalar()


def query(sql: str, **p) -> list[dict]:
    with engine().connect() as c:
        return [dict(r) for r in c.execute(text(sql), p).mappings().all()]


def query_one(sql: str, **p):
    rows = query(sql, **p)
    return rows[0] if rows else None


def df(sql: str, **p) -> pd.DataFrame:
    with engine().connect() as c:
        return pd.read_sql_query(text(sql), c, params=p)


# ---------- 초기화 ----------
def init_db():
    pk = "SERIAL PRIMARY KEY" if is_pg() else "INTEGER PRIMARY KEY AUTOINCREMENT"
    stmts = [
        f"""CREATE TABLE IF NOT EXISTS users(
          id {pk}, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
          pw_hash TEXT NOT NULL, salt TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'user', is_active INTEGER NOT NULL DEFAULT 1,
          email_verified INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, deleted_at TEXT)""",
        f"""CREATE TABLE IF NOT EXISTS orders(
          id {pk}, user_id INTEGER NOT NULL REFERENCES users(id),
          chart_key TEXT NOT NULL, category TEXT NOT NULL, birth_summary TEXT,
          amount INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'paid',
          pg_provider TEXT, pg_tx_id TEXT, content TEXT, created_at TEXT NOT NULL)""",
        "CREATE INDEX IF NOT EXISTS idx_orders_lookup ON orders(user_id, chart_key, category)",
        "CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        f"""CREATE TABLE IF NOT EXISTS events(
          id {pk}, kind TEXT NOT NULL, user_id INTEGER, category TEXT, created_at TEXT NOT NULL)""",
        f"""CREATE TABLE IF NOT EXISTS email_codes(
          id {pk}, email TEXT NOT NULL, purpose TEXT NOT NULL, code_hash TEXT NOT NULL,
          salt TEXT NOT NULL, expires_at TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL)""",
        "CREATE INDEX IF NOT EXISTS idx_codes_lookup ON email_codes(email, purpose)",
    ]
    for s in stmts:
        execute(s)
    # 이전 버전 DB 마이그레이션: 기존 회원은 인증된 것으로 간주
    cols = [c["name"] for c in inspect(engine()).get_columns("users")]
    if "email_verified" not in cols:
        execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1")
    if "deleted_at" not in cols:
        execute("ALTER TABLE users ADD COLUMN deleted_at TEXT")

    admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    admin_pw = os.environ.get("ADMIN_PASSWORD", "")
    if admin_email:
        # Secrets의 ADMIN_EMAIL = 운영자 본인. 이미 가입한 계정이면 관리자로 승격, 없으면 ADMIN_PASSWORD로 생성
        u = query_one("SELECT id FROM users WHERE email=:e", e=admin_email)
        if u:
            execute("UPDATE users SET role='admin', email_verified=1, is_active=1 WHERE id=:i", i=u["id"])
        elif admin_pw:
            try:
                create_user(admin_email, "관리자", admin_pw, role="admin", verified=True)
            except ValueError:
                pass
        if admin_email != DEFAULT_ADMIN[0]:  # 공개된 기본 관리자 계정은 보안상 비활성화
            execute("UPDATE users SET is_active=0 WHERE email=:e", e=DEFAULT_ADMIN[0])
    elif not query_one("SELECT id FROM users WHERE role='admin'"):
        try:
            create_user(DEFAULT_ADMIN[0], "관리자", DEFAULT_ADMIN[1], role="admin", verified=True)
        except ValueError:
            pass


def backend_label() -> str:
    return "PostgreSQL (영구 저장)" if is_pg() else "SQLite 파일 (임시 — 클라우드에서는 재시작 시 초기화될 수 있음)"


# ---------- 회원 ----------
def _hash(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()


def _public(u: dict) -> dict:
    return {k: u[k] for k in ("id", "email", "name", "role")}


def create_user(email: str, name: str, pw: str, role: str = "user", verified: bool = False) -> dict:
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError("이메일 형식이 올바르지 않습니다.")
    if len(pw) < 8:
        raise ValueError("비밀번호는 8자 이상이어야 합니다.")
    if not name.strip():
        raise ValueError("이름(닉네임)을 입력해 주세요.")
    salt = secrets.token_hex(16)
    existing = query_one("SELECT id, email_verified FROM users WHERE email=:e", e=email)
    if existing:
        if existing["email_verified"]:
            raise ValueError("이미 가입된 이메일입니다.")
        # 인증을 끝내지 않은 가입 시도: 정보를 갱신해 다시 인증 진행
        execute("UPDATE users SET name=:n, pw_hash=:h, salt=:s WHERE id=:i",
                n=name.strip(), h=_hash(pw, salt), s=salt, i=existing["id"])
        return _public(query_one("SELECT * FROM users WHERE id=:i", i=existing["id"]))
    try:
        uid = insert_returning_id(
            "INSERT INTO users(email,name,pw_hash,salt,role,email_verified,created_at) "
            "VALUES(:e,:n,:h,:s,:r,:v,:t)",
            e=email, n=name.strip(), h=_hash(pw, salt), s=salt, r=role, v=1 if verified else 0, t=now(),
        )
    except IntegrityError:
        raise ValueError("이미 가입된 이메일입니다.")
    return _public(query_one("SELECT * FROM users WHERE id=:i", i=uid))


def login(email: str, pw: str):
    """returns (status, user): status = ok | bad | inactive | unverified"""
    u = query_one("SELECT * FROM users WHERE email=:e", e=email.strip().lower())
    if not u or not hmac.compare_digest(_hash(pw, u["salt"]), u["pw_hash"]):
        return "bad", None
    if not u["is_active"]:
        return "inactive", None
    if not u["email_verified"]:
        return "unverified", _public(u)
    if u["role"] != "admin" and _is_owner_email(u["email"]):
        set_user_role(u["id"], "admin")
        u["role"] = "admin"
    return "ok", _public(u)


def authenticate(email: str, pw: str):
    status, u = login(email, pw)
    return u if status == "ok" else None


def get_user(uid: int):
    u = query_one("SELECT * FROM users WHERE id=:i", i=uid)
    return _public(u) if u else None


def get_user_by_email(email: str):
    u = query_one("SELECT * FROM users WHERE email=:e", e=email.strip().lower())
    return _public(u) if u else None


def _is_owner_email(email: str) -> bool:
    return bool(os.environ.get("ADMIN_EMAIL")) and email.strip().lower() == os.environ["ADMIN_EMAIL"].strip().lower()


def mark_verified(email: str):
    email = email.strip().lower()
    execute("UPDATE users SET email_verified=1 WHERE email=:e", e=email)
    if _is_owner_email(email):  # 운영자 이메일은 인증을 마치면 자동으로 관리자
        execute("UPDATE users SET role='admin' WHERE email=:e", e=email)


def set_email_verified(uid: int, verified: bool):
    execute("UPDATE users SET email_verified=:v WHERE id=:i", v=1 if verified else 0, i=uid)


def set_user_role(uid: int, role: str):
    execute("UPDATE users SET role=:r WHERE id=:i", r=role, i=uid)


def change_password(uid: int, new_pw: str):
    if len(new_pw) < 8:
        raise ValueError("비밀번호는 8자 이상이어야 합니다.")
    salt = secrets.token_hex(16)
    execute("UPDATE users SET pw_hash=:h, salt=:s WHERE id=:i", h=_hash(new_pw, salt), s=salt, i=uid)


def update_name(uid: int, name: str):
    name = name.strip()
    if not name:
        raise ValueError("이름(닉네임)을 입력해 주세요.")
    execute("UPDATE users SET name=:n WHERE id=:i", n=name[:20], i=uid)


def change_password_checked(uid: int, old_pw: str, new_pw: str):
    u = query_one("SELECT * FROM users WHERE id=:i", i=uid)
    if not u or not hmac.compare_digest(_hash(old_pw, u["salt"]), u["pw_hash"]):
        raise ValueError("현재 비밀번호가 일치하지 않습니다.")
    change_password(uid, new_pw)


def withdraw_user(uid: int, pw: str):
    """회원 탈퇴: 개인정보(이메일·이름·생년월일·풀이 본문)는 삭제/익명화하고,
    결제 기록(금액·상태·거래ID·일시)만 남깁니다(전자상거래 관련 기록 보관 목적)."""
    u = query_one("SELECT * FROM users WHERE id=:i", i=uid)
    if not u or u.get("deleted_at"):
        raise ValueError("계정을 찾을 수 없습니다.")
    if u["role"] == "admin":
        raise ValueError("관리자 계정은 탈퇴할 수 없습니다. 관리자 권한을 먼저 해제해 주세요.")
    if not hmac.compare_digest(_hash(pw, u["salt"]), u["pw_hash"]):
        raise ValueError("비밀번호가 일치하지 않습니다.")
    salt = secrets.token_hex(16)
    execute("DELETE FROM email_codes WHERE email=:e", e=u["email"])
    execute("UPDATE orders SET birth_summary=NULL, content=NULL WHERE user_id=:i", i=uid)
    execute("UPDATE events SET user_id=NULL WHERE user_id=:i", i=uid)
    execute(
        "UPDATE users SET email=:a, name='탈퇴회원', pw_hash=:h, salt=:s, is_active=0, email_verified=0, deleted_at=:t WHERE id=:i",
        a=f"deleted-{uid}@deleted.invalid", h=secrets.token_hex(32), s=salt, t=now(), i=uid,
    )
    log_event("withdraw")


def set_user_active(uid: int, active: bool):
    execute("UPDATE users SET is_active=:a WHERE id=:i", a=1 if active else 0, i=uid)


# ---------- 이메일 인증코드 ----------
def _code_hash(code: str, salt: str) -> str:
    return hashlib.sha256((salt + code).encode()).hexdigest()


def issue_code(email: str, purpose: str) -> str:
    """6자리 코드 발급(평문은 메일로만 전달, DB에는 해시 저장). 60초 내 재발급 제한."""
    email = email.strip().lower()
    last = query_one(
        "SELECT created_at FROM email_codes WHERE email=:e AND purpose=:p ORDER BY id DESC", e=email, p=purpose
    )
    if last and (datetime.now(KST) - _parse(last["created_at"])).total_seconds() < CODE_COOLDOWN_SEC:
        raise ValueError(f"인증코드는 {CODE_COOLDOWN_SEC}초에 한 번만 받을 수 있어요. 방금 보낸 코드를 확인해 주세요.")
    code = f"{secrets.randbelow(1_000_000):06d}"
    salt = secrets.token_hex(8)
    execute("DELETE FROM email_codes WHERE email=:e AND purpose=:p", e=email, p=purpose)
    execute(
        "INSERT INTO email_codes(email,purpose,code_hash,salt,expires_at,attempts,created_at) "
        "VALUES(:e,:p,:h,:s,:x,0,:t)",
        e=email, p=purpose, h=_code_hash(code, salt), s=salt,
        x=(datetime.now(KST) + timedelta(minutes=CODE_TTL_MIN)).strftime("%Y-%m-%d %H:%M:%S"), t=now(),
    )
    return code


def verify_code(email: str, purpose: str, code: str):
    """returns (성공여부, 오류메시지). 성공 시 코드는 즉시 폐기."""
    email = email.strip().lower()
    row = query_one("SELECT * FROM email_codes WHERE email=:e AND purpose=:p ORDER BY id DESC", e=email, p=purpose)
    if not row:
        return False, "인증코드를 먼저 받아 주세요."
    if now() > row["expires_at"]:
        return False, "인증코드가 만료되었습니다. 새 코드를 받아 주세요."
    if row["attempts"] >= CODE_MAX_ATTEMPTS:
        return False, "시도 횟수를 초과했습니다. 새 코드를 받아 주세요."
    if not hmac.compare_digest(_code_hash(code.strip(), row["salt"]), row["code_hash"]):
        execute("UPDATE email_codes SET attempts=attempts+1 WHERE id=:i", i=row["id"])
        left = CODE_MAX_ATTEMPTS - row["attempts"] - 1
        return False, f"인증코드가 일치하지 않습니다. (남은 시도 {left}회)"
    execute("DELETE FROM email_codes WHERE id=:i", i=row["id"])
    return True, ""


# ---------- 주문 ----------
def find_order(user_id: int, chart_key: str, category: str):
    return query_one(
        "SELECT * FROM orders WHERE user_id=:u AND chart_key=:k AND category=:c AND status='paid' ORDER BY id DESC",
        u=user_id, k=chart_key, c=category,
    )


def create_order(user_id, chart_key, category, birth_summary, amount, provider, tx_id, content) -> int:
    return insert_returning_id(
        "INSERT INTO orders(user_id,chart_key,category,birth_summary,amount,status,pg_provider,pg_tx_id,content,created_at)"
        " VALUES(:u,:k,:c,:b,:a,'paid',:p,:x,:t,:ts)",
        u=user_id, k=chart_key, c=category, b=birth_summary, a=amount, p=provider, x=tx_id, t=content, ts=now(),
    )


def user_orders(user_id: int):
    return query("SELECT * FROM orders WHERE user_id=:u ORDER BY id DESC", u=user_id)


def set_order_status(order_id: int, status: str):
    execute("UPDATE orders SET status=:s WHERE id=:i", s=status, i=order_id)


# ---------- 설정 / 이벤트 ----------
def get_setting(key: str, default: str = "") -> str:
    r = query_one("SELECT value FROM settings WHERE key=:k", k=key)
    return r["value"] if r else default


def set_setting(key: str, value: str):
    execute(
        "INSERT INTO settings(key,value) VALUES(:k,:v) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        k=key, v=value,
    )


def log_event(kind: str, user_id=None, category=None):
    execute("INSERT INTO events(kind,user_id,category,created_at) VALUES(:k,:u,:c,:t)",
            k=kind, u=user_id, c=category, t=now())


# ---------- 관리자 통계 ----------
def admin_orders_df() -> pd.DataFrame:
    return df(
        "SELECT o.id, o.created_at, u.email, u.name, o.category, o.birth_summary, o.amount, o.status, "
        "o.pg_provider, o.pg_tx_id FROM orders o JOIN users u ON u.id=o.user_id ORDER BY o.id DESC"
    )


def admin_users_df() -> pd.DataFrame:
    return df(
        "SELECT u.id, u.email, u.name, u.role, u.is_active, u.email_verified, u.created_at, "
        "COUNT(CASE WHEN o.status='paid' THEN 1 END) AS paid_orders, "
        "COALESCE(SUM(CASE WHEN o.status='paid' THEN o.amount END),0) AS total_paid "
        "FROM users u LEFT JOIN orders o ON o.user_id=u.id WHERE u.deleted_at IS NULL GROUP BY u.id ORDER BY u.id DESC"
    )


def event_counts() -> dict:
    return {r["kind"]: r["n"] for r in query("SELECT kind, COUNT(*) AS n FROM events GROUP BY kind")}
