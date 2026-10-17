"""SQLite 데이터 계층: 회원, 주문, 설정, 이벤트(퍼널 분석)."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

DB_PATH = os.environ.get("SAJU_DB", "saju.db")
KST = ZoneInfo("Asia/Seoul")
DEFAULT_ADMIN = ("admin@saju.local", "admin1234!")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
  pw_hash TEXT NOT NULL, salt TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user', is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  chart_key TEXT NOT NULL, category TEXT NOT NULL, birth_summary TEXT,
  amount INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'paid',
  pg_provider TEXT, pg_tx_id TEXT, content TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_orders_lookup ON orders(user_id, chart_key, category);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
  user_id INTEGER, category TEXT, created_at TEXT NOT NULL);
"""


def now() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


def _c():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def execute(sql, params=()):
    with closing(_c()) as c:
        cur = c.execute(sql, params)
        c.commit()
        return cur.lastrowid


def query(sql, params=()):
    with closing(_c()) as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def df(sql, params=()):
    with closing(_c()) as c:
        return pd.read_sql_query(sql, c, params=params)


# ---------- 초기화 ----------
def init_db():
    with closing(_c()) as c:
        c.executescript(SCHEMA)
        c.commit()
    if not query_one("SELECT id FROM users WHERE role='admin'"):
        email = os.environ.get("ADMIN_EMAIL", DEFAULT_ADMIN[0])
        pw = os.environ.get("ADMIN_PASSWORD", DEFAULT_ADMIN[1])
        try:
            create_user(email, "관리자", pw, role="admin")
        except ValueError:
            pass


# ---------- 회원 ----------
def _hash(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()


def _public(u: dict) -> dict:
    return {k: u[k] for k in ("id", "email", "name", "role")}


def create_user(email: str, name: str, pw: str, role: str = "user") -> dict:
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError("이메일 형식이 올바르지 않습니다.")
    if len(pw) < 8:
        raise ValueError("비밀번호는 8자 이상이어야 합니다.")
    if not name.strip():
        raise ValueError("이름(닉네임)을 입력해 주세요.")
    salt = secrets.token_hex(16)
    try:
        uid = execute(
            "INSERT INTO users(email,name,pw_hash,salt,role,created_at) VALUES(?,?,?,?,?,?)",
            (email, name.strip(), _hash(pw, salt), salt, role, now()),
        )
    except sqlite3.IntegrityError:
        raise ValueError("이미 가입된 이메일입니다.")
    return _public(query_one("SELECT * FROM users WHERE id=?", (uid,)))


def authenticate(email: str, pw: str):
    u = query_one("SELECT * FROM users WHERE email=?", (email.strip().lower(),))
    if not u or not u["is_active"]:
        return None
    if hmac.compare_digest(_hash(pw, u["salt"]), u["pw_hash"]):
        return _public(u)
    return None


def get_user(uid: int):
    u = query_one("SELECT * FROM users WHERE id=?", (uid,))
    return _public(u) if u else None


def change_password(uid: int, new_pw: str):
    if len(new_pw) < 8:
        raise ValueError("비밀번호는 8자 이상이어야 합니다.")
    salt = secrets.token_hex(16)
    execute("UPDATE users SET pw_hash=?, salt=? WHERE id=?", (_hash(new_pw, salt), salt, uid))


def set_user_active(uid: int, active: bool):
    execute("UPDATE users SET is_active=? WHERE id=?", (1 if active else 0, uid))


# ---------- 주문 ----------
def find_order(user_id: int, chart_key: str, category: str):
    return query_one(
        "SELECT * FROM orders WHERE user_id=? AND chart_key=? AND category=? AND status='paid' ORDER BY id DESC",
        (user_id, chart_key, category),
    )


def create_order(user_id, chart_key, category, birth_summary, amount, provider, tx_id, content) -> int:
    return execute(
        "INSERT INTO orders(user_id,chart_key,category,birth_summary,amount,status,pg_provider,pg_tx_id,content,created_at)"
        " VALUES(?,?,?,?,?,'paid',?,?,?,?)",
        (user_id, chart_key, category, birth_summary, amount, provider, tx_id, content, now()),
    )


def user_orders(user_id: int):
    return query("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (user_id,))


def set_order_status(order_id: int, status: str):
    execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))


# ---------- 설정 / 이벤트 ----------
def get_setting(key: str, default: str = "") -> str:
    r = query_one("SELECT value FROM settings WHERE key=?", (key,))
    return r["value"] if r else default


def set_setting(key: str, value: str):
    execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def log_event(kind: str, user_id=None, category=None):
    execute("INSERT INTO events(kind,user_id,category,created_at) VALUES(?,?,?,?)", (kind, user_id, category, now()))


# ---------- 관리자 통계 ----------
def admin_orders_df() -> pd.DataFrame:
    return df(
        "SELECT o.id, o.created_at, u.email, u.name, o.category, o.birth_summary, o.amount, o.status, o.pg_provider, o.pg_tx_id "
        "FROM orders o JOIN users u ON u.id=o.user_id ORDER BY o.id DESC"
    )


def admin_users_df() -> pd.DataFrame:
    return df(
        "SELECT u.id, u.email, u.name, u.role, u.is_active, u.created_at, "
        "COUNT(CASE WHEN o.status='paid' THEN 1 END) AS paid_orders, "
        "COALESCE(SUM(CASE WHEN o.status='paid' THEN o.amount END),0) AS total_paid "
        "FROM users u LEFT JOIN orders o ON o.user_id=u.id GROUP BY u.id ORDER BY u.id DESC"
    )


def event_counts() -> dict:
    return {r["kind"]: r["n"] for r in query("SELECT kind, COUNT(*) n FROM events GROUP BY kind")}
