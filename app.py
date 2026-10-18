"""AI 사주 서비스 (Streamlit).  실행: streamlit run app.py"""
import json
import os
from datetime import date, time

import pandas as pd
import streamlit as st

import db
import interpret as itp
import mailer
import payments
import saju_engine as se

st.set_page_config(page_title="AI 사주", page_icon="🔮", layout="centered")


@st.cache_resource
def _init_db():
    db.init_db()
    return True


_init_db()

APP_VERSION = "0.4.0"
CATS = itp.CATEGORIES
PAGES: dict = {}


# ---------- 공통 헬퍼 ----------
def user():
    return st.session_state.get("user")


def won(n) -> str:
    return f"{int(n):,}원"


def price() -> int:
    return int(db.get_setting("price", "3900"))


def service_name() -> str:
    return db.get_setting("service_name", "AI 사주")


def enabled_cats() -> list:
    try:
        keys = json.loads(db.get_setting("enabled_cats", json.dumps(list(CATS))))
    except Exception:
        keys = list(CATS)
    return [k for k in CATS if k in keys]


def pillar_html(label, p) -> str:
    if p is None:
        return f"<div style='text-align:center;opacity:.5;padding:18px 0'>{label}<br>미상</div>"
    c1, c2 = se.EL_COLOR[p["stem_el"]], se.EL_COLOR[p["br_el"]]
    return (
        "<div style='text-align:center;border:1px solid #8884;border-radius:12px;padding:10px 4px'>"
        f"<div style='font-size:12px;opacity:.7'>{label}</div>"
        f"<div style='font-size:12px'>{p['stem_tg']}</div>"
        f"<div style='font-size:34px;font-weight:700;color:{c1}'>{p['stem_zh']}</div>"
        f"<div style='font-size:11px;opacity:.7'>{p['stem_ko']}({p['stem_el_ko']})</div>"
        f"<div style='font-size:34px;font-weight:700;color:{c2}'>{p['br_zh']}</div>"
        f"<div style='font-size:11px;opacity:.7'>{p['br_ko']}({p['br_el_ko']})</div>"
        f"<div style='font-size:12px'>{p['br_tg']}</div></div>"
    )


# ---------- 결제 다이얼로그 ----------
@st.dialog("상세 풀이 결제")
def pay_dialog(cat: str):
    ctx, u = st.session_state["ctx"], user()
    icon, label = CATS[cat]
    amount = price()
    st.markdown(f"**{icon} {label}** 전체 풀이 · **{won(amount)}** (1건)")
    if payments.MODE == "mock":
        st.warning("테스트 결제 모드입니다. 실제로 청구되지 않습니다.")
    agree = st.checkbox("디지털 콘텐츠 특성상 열람 후 청약철회가 제한될 수 있음에 동의합니다.")
    if st.button("결제하기", type="primary", disabled=not agree, width="stretch"):
        try:
            with st.spinner("결제 및 풀이 생성 중..."):
                ok, tx, provider = payments.charge(u, amount, f"{label} 풀이")
                if ok:
                    content = itp.generate_full(
                        ctx["chart"], cat, ctx["name"], use_llm=db.get_setting("use_llm", "0") == "1"
                    )
                    db.create_order(u["id"], ctx["key"], cat, ctx["summary"], amount, provider, tx, content)
                    db.log_event("paid", u["id"], cat)
        except NotImplementedError as e:
            st.error(str(e))
            return
        st.rerun()


# ---------- 홈 ----------
def category_block(ctx, cat):
    icon, label = CATS[cat]
    pv = itp.preview(ctx["chart"], cat)
    u = user()
    st.subheader(f"{icon} {label}")
    st.markdown(f"**{pv['head']}**")
    st.write(pv["teaser"] + " …")

    order = db.find_order(u["id"], ctx["key"], cat) if u else None
    if order:
        with st.expander("📖 전체 풀이 보기", expanded=True):
            st.markdown(order["content"])
        return

    with st.container(border=True):
        st.markdown("🔒 **전체 풀이에 포함된 내용**")
        st.markdown(" · ".join(itp.LOCKED_TITLES))
        if not u:
            st.caption("상세 풀이는 회원만 이용할 수 있어요.")
            if st.button("회원가입 / 로그인하고 열어보기", key=f"login_{cat}", width="stretch"):
                st.switch_page(PAGES["auth"])
        else:
            if st.button(f"🔓 {won(price())} 결제하고 전체 보기", key=f"pay_{cat}", type="primary",
                         width="stretch"):
                db.log_event("pay_open", u["id"], cat)
                pay_dialog(cat)


def home():
    flash = st.session_state.pop("flash", None)
    if flash:
        st.success(flash)
    st.title(f"🔮 {service_name()}")
    st.caption("생년월일시로 보는 직업운 · 재물운 · 연애운 — 요약은 누구나 무료, 상세 풀이는 회원 전용")

    with st.form("birth"):
        name = st.text_input("이름 (선택)", max_chars=20)
        c1, c2 = st.columns(2)
        gender = c1.radio("성별", ["여성", "남성"], horizontal=True)
        cal = c2.radio("달력", ["양력", "음력"], horizontal=True)
        bd = st.date_input("생년월일", value=date(1995, 1, 1), min_value=date(1920, 1, 1),
                           max_value=date.today(), format="YYYY/MM/DD")
        leap = st.checkbox("음력 윤달")
        unknown = st.checkbox("태어난 시간을 몰라요")
        bt = st.time_input("태어난 시간", value=time(12, 0), step=60)
        adj = st.checkbox("진태양시 보정 (-30분)")
        go = st.form_submit_button("내 사주 보기", type="primary", width="stretch")

    if go:
        hour, minute = (None, 0) if unknown else (bt.hour, bt.minute)
        try:
            chart = se.compute_chart(bd.year, bd.month, bd.day, hour, minute, gender, cal, leap, adj)
        except Exception:
            st.error("입력하신 날짜를 확인할 수 없어요. (음력 윤달/날짜를 다시 확인해 주세요)")
            chart = None
        if chart:
            tstr = "시간미상" if unknown else f"{bt.hour:02d}:{bt.minute:02d}"
            st.session_state["ctx"] = {
                "chart": chart, "name": name.strip(),
                "key": se.chart_key(bd.year, bd.month, bd.day, hour, minute, gender, cal, leap, adj),
                "summary": f"{bd.isoformat()} {tstr} {cal} {gender}",
            }
            db.log_event("chart", (user() or {}).get("id"))

    ctx = st.session_state.get("ctx")
    if not ctx:
        return
    chart = ctx["chart"]

    st.divider()
    st.subheader(f"{ctx['name'] + '님의 ' if ctx['name'] else ''}사주 명식")
    st.caption(f"양력 환산 {chart['solar']} · 일간 {chart['day_master']['ko']}({chart['day_master']['zh']}, {chart['day_master']['el']}) · {chart['strength']}")
    cols = st.columns(4)
    for col, p, lab in zip(cols, chart["pillars"], se.LABELS):
        col.markdown(pillar_html(lab, p), unsafe_allow_html=True)

    st.markdown("**오행 분포**")
    st.bar_chart(pd.DataFrame({"개수": chart["el_count"]}), height=180)
    st.divider()

    for cat in enabled_cats():
        category_block(ctx, cat)
        st.divider()
    st.caption(itp.DISCLAIMER)


# ---------- 로그인 / 회원가입 / 이메일 인증 ----------
PURPOSE_LABEL = {"signup": "회원가입", "reset": "비밀번호 재설정"}


def send_code(email: str, purpose: str):
    """인증코드 발급·메일 발송. returns (알림레벨, 메시지)"""
    try:
        code = db.issue_code(email, purpose)
    except ValueError as e:  # 60초 쿨다운: 이미 보낸 코드가 유효
        return "warning", str(e)
    if mailer.configured():
        try:
            mailer.send_code(email, code, PURPOSE_LABEL[purpose], service_name())
        except Exception as e:
            return "error", f"인증 메일 발송에 실패했습니다. 잠시 후 다시 시도해 주세요. ({type(e).__name__})"
        return "success", f"{email} 로 인증코드를 보냈습니다. 10분 안에 입력해 주세요. 메일이 안 보이면 스팸함도 확인해 주세요."
    if os.environ.get("ALLOW_DEV_CODE") == "1":  # 개발/테스트 전용: SMTP 없이 화면에 코드 표시
        return "warning", f"[개발 모드] 인증코드: {code}"
    return "error", "메일 발송 설정(SMTP)이 아직 되어 있지 않습니다. 운영자에게 문의해 주세요."


def notice():
    lvl, msg = st.session_state.pop("auth_notice", (None, None))
    if msg:
        getattr(st, lvl)(msg)


def verify_panel(email: str):
    st.title("📧 이메일 인증")
    notice()
    st.write(f"**{email}** 로 보낸 6자리 인증코드를 입력해 주세요.")
    with st.form("verify"):
        code = st.text_input("인증코드", max_chars=6)
        ok = st.form_submit_button("인증하기", type="primary", width="stretch")
    if ok:
        good, err = db.verify_code(email, "signup", code)
        if good:
            db.mark_verified(email)
            u = db.get_user_by_email(email)
            db.log_event("signup", u["id"])
            st.session_state.pop("verify_email", None)
            st.session_state["user"] = u
            st.switch_page(PAGES["home"])
        else:
            st.error(err)
    c1, c2 = st.columns(2)
    if c1.button("인증코드 다시 받기", width="stretch"):
        st.session_state["auth_notice"] = send_code(email, "signup")
        st.rerun()
    if c2.button("처음으로", width="stretch"):
        st.session_state.pop("verify_email", None)
        st.rerun()


def reset_tab():
    email = st.session_state.get("reset_email")
    if not email:
        with st.form("reset_req"):
            e = st.text_input("가입한 이메일")
            ok = st.form_submit_button("인증코드 보내기", width="stretch")
        if ok:
            u = db.get_user_by_email(e) if e else None
            if u:
                st.session_state["auth_notice"] = send_code(u["email"], "reset")
            else:  # 가입 여부를 노출하지 않기 위해 같은 문구 사용
                st.session_state["auth_notice"] = ("success", "가입된 이메일이라면 인증코드를 보냈습니다.")
            st.session_state["reset_email"] = e.strip().lower()
            st.rerun()
        return
    notice()
    with st.form("reset_do"):
        code = st.text_input("인증코드", max_chars=6)
        npw = st.text_input("새 비밀번호 (8자 이상)", type="password")
        ok = st.form_submit_button("비밀번호 변경", type="primary", width="stretch")
    if ok:
        u = db.get_user_by_email(email)
        good, err = db.verify_code(email, "reset", code) if u else (False, "인증코드가 일치하지 않습니다.")
        if good:
            try:
                db.change_password(u["id"], npw)
                db.mark_verified(email)  # 메일 수신을 확인했으므로 인증 완료로 처리
                st.session_state.pop("reset_email", None)
                st.success("비밀번호를 변경했습니다. '로그인' 탭에서 로그인해 주세요.")
            except ValueError as e:
                st.error(str(e))
        else:
            st.error(err)
    if st.button("처음으로", key="reset_back"):
        st.session_state.pop("reset_email", None)
        st.rerun()


def auth_page():
    if st.session_state.get("verify_email"):
        verify_panel(st.session_state["verify_email"])
        return

    st.title("🔑 로그인 / 회원가입")
    notice()
    tab_in, tab_up, tab_pw = st.tabs(["로그인", "회원가입", "비밀번호 찾기"])

    with tab_in:
        with st.form("login"):
            email = st.text_input("이메일")
            pw = st.text_input("비밀번호", type="password")
            ok = st.form_submit_button("로그인", type="primary", width="stretch")
        if ok:
            fails = st.session_state.get("fails", 0)
            if fails >= 5:
                st.error("로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.")
            else:
                status, u = db.login(email, pw)
                if status == "ok":
                    st.session_state["user"] = u
                    st.session_state["fails"] = 0
                    st.switch_page(PAGES["home"])
                elif status == "unverified":  # 가입은 했지만 메일 인증을 끝내지 않음
                    st.session_state["verify_email"] = u["email"]
                    st.session_state["auth_notice"] = send_code(u["email"], "signup")
                    st.rerun()
                elif status == "inactive":
                    st.error("비활성화된 계정입니다. 운영자에게 문의해 주세요.")
                else:
                    st.session_state["fails"] = fails + 1
                    st.error("이메일 또는 비밀번호가 올바르지 않습니다.")

    with tab_up:
        with st.form("signup"):
            email = st.text_input("이메일", key="su_email")
            name = st.text_input("이름(닉네임)", key="su_name", max_chars=20)
            pw = st.text_input("비밀번호 (8자 이상)", type="password", key="su_pw")
            pw2 = st.text_input("비밀번호 확인", type="password", key="su_pw2")
            agree = st.checkbox("이용약관 및 개인정보 수집·이용에 동의합니다. (필수)")
            ok = st.form_submit_button("인증코드 받고 가입하기", type="primary", width="stretch")
        if ok:
            if not agree:
                st.error("필수 약관에 동의해 주세요.")
            elif pw != pw2:
                st.error("비밀번호 확인이 일치하지 않습니다.")
            else:
                try:
                    u = db.create_user(email, name, pw)
                except ValueError as e:
                    st.error(str(e))
                else:
                    st.session_state["verify_email"] = u["email"]
                    st.session_state["auth_notice"] = send_code(u["email"], "signup")
                    st.rerun()

    with tab_pw:
        reset_tab()


# ---------- 마이페이지 ----------
def mypage():
    u = user()
    st.title("👤 마이페이지")
    t_orders, t_id, t_pw, t_out = st.tabs(["구매내역", "아이디", "비밀번호", "회원탈퇴"])

    with t_orders:
        orders = db.user_orders(u["id"])
        if not orders:
            st.info("아직 구매한 풀이가 없어요. 사주 보기에서 시작해 보세요.")
        for o in orders:
            icon, label = CATS.get(o["category"], ("", o["category"]))
            badge = "" if o["status"] == "paid" else " (환불됨)"
            with st.expander(f"{icon} {label} · {o['birth_summary']} · {won(o['amount'])} · {o['created_at']}{badge}"):
                if o["status"] == "paid":
                    st.markdown(o["content"])
                else:
                    st.caption("환불 처리된 주문입니다.")

    with t_id:
        st.markdown("**아이디(로그인 이메일)**")
        st.code(u["email"], language=None)
        st.caption("아이디는 가입한 이메일 주소이며 이 화면에서 변경할 수 없어요.")
        with st.form("rename"):
            new_name = st.text_input("이름(닉네임)", value=u["name"], max_chars=20)
            if st.form_submit_button("이름 변경", width="stretch"):
                try:
                    db.update_name(u["id"], new_name)
                    st.session_state["user"]["name"] = new_name.strip()[:20]
                    st.success("이름을 변경했습니다.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    with t_pw:
        with st.form("chpw_user"):
            old = st.text_input("현재 비밀번호", type="password")
            new = st.text_input("새 비밀번호 (8자 이상)", type="password")
            new2 = st.text_input("새 비밀번호 확인", type="password")
            ok = st.form_submit_button("비밀번호 변경", type="primary", width="stretch")
        if ok:
            if new != new2:
                st.error("새 비밀번호 확인이 일치하지 않습니다.")
            else:
                try:
                    db.change_password_checked(u["id"], old, new)
                    st.success("비밀번호를 변경했습니다.")
                except ValueError as e:
                    st.error(str(e))

    with t_out:
        if u["role"] == "admin":
            st.info("관리자 계정은 이 화면에서 탈퇴할 수 없습니다.")
        else:
            st.warning(
                "탈퇴하면 이메일·이름·입력하신 생년월일 정보와 **구매한 풀이 내용이 삭제되어 다시 볼 수 없습니다.** "
                "결제 기록(금액·일시·거래번호)은 관련 법령상 보관이 필요할 수 있어 개인정보를 제외하고 남습니다."
            )
            with st.form("withdraw"):
                pw = st.text_input("비밀번호 확인", type="password")
                agree = st.checkbox("위 내용을 확인했으며 탈퇴에 동의합니다.")
                ok = st.form_submit_button("탈퇴하기", type="primary", width="stretch")
            if ok:
                if not agree:
                    st.error("탈퇴 동의에 체크해 주세요.")
                else:
                    try:
                        db.withdraw_user(u["id"], pw)
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        for k in ("user", "ctx", "verify_email", "reset_email"):
                            st.session_state.pop(k, None)
                        st.session_state["flash"] = "회원 탈퇴가 완료되었습니다. 이용해 주셔서 감사합니다."
                        st.switch_page(PAGES["home"])


# ---------- 관리자 ----------
def admin_page():
    me = db.get_user(user()["id"])
    if not me or me["role"] != "admin":
        st.error("관리자만 접근할 수 있습니다.")
        return
    st.title("🛠️ 관리자")
    if not db.is_pg():
        st.warning("현재 임시 파일 DB(SQLite)를 사용 중입니다. 클라우드에서는 앱이 재시작되면 회원·주문 데이터가 사라질 수 있어요. "
                   "Secrets에 DATABASE_URL을 설정하세요. (내 컴퓨터 테스트 중이라면 무시해도 됩니다.)")
    if not mailer.configured():
        st.warning("이메일 발송(SMTP)이 설정되지 않아 인증코드를 보낼 수 없습니다. Secrets에 SMTP_* 값을 설정하세요.")
    if db.authenticate(*db.DEFAULT_ADMIN):
        st.warning("기본 관리자 비밀번호를 사용 중입니다. '설정' 탭에서 즉시 변경하세요.")

    orders = db.admin_orders_df()
    users = db.admin_users_df()
    paid = orders[orders["status"] == "paid"] if len(orders) else orders
    t_dash, t_orders, t_users, t_set = st.tabs(["대시보드", "주문/환불", "회원", "설정"])

    with t_dash:
        today = db.now()[:10]
        total = int(paid["amount"].sum()) if len(paid) else 0
        today_rev = int(paid[paid["created_at"].str.startswith(today)]["amount"].sum()) if len(paid) else 0
        buyers = paid["email"].nunique() if len(paid) else 0
        members = int(((users["role"] == "user") & (users["email_verified"] == 1)).sum())
        c = st.columns(4)
        c[0].metric("누적 매출", won(total))
        c[1].metric("오늘 매출", won(today_rev))
        c[2].metric("회원 수", f"{members:,}명")
        c[3].metric("구매 전환율", f"{(buyers / members * 100 if members else 0):.1f}%")
        if len(paid):
            daily = paid.assign(date=paid["created_at"].str[:10]).groupby("date")["amount"].sum()
            st.markdown("**일별 매출**")
            st.bar_chart(daily)
            st.markdown("**카테고리별 매출**")
            cat_rev = paid.groupby("category")["amount"].sum().rename(lambda k: CATS.get(k, ("", k))[1])
            st.bar_chart(cat_rev)
        ev = db.event_counts()
        st.markdown("**퍼널**")
        f = st.columns(4)
        f[0].metric("사주 조회", ev.get("chart", 0))
        f[1].metric("가입", ev.get("signup", 0))
        f[2].metric("결제창 오픈", ev.get("pay_open", 0))
        f[3].metric("결제 완료", ev.get("paid", 0))

    with t_orders:
        show = orders.drop(columns=["pg_tx_id"]) if len(orders) else orders
        st.dataframe(show, width="stretch", hide_index=True)
        if len(orders):
            st.download_button("주문 CSV 다운로드", orders.to_csv(index=False).encode("utf-8-sig"), "orders.csv", "text/csv")
            st.markdown("**환불 처리**")
            oid = st.selectbox("주문 ID", orders[orders["status"] == "paid"]["id"].tolist() or [None])
            if oid and st.button("환불 처리"):
                row = orders[orders["id"] == oid].iloc[0]
                try:
                    if payments.refund(row["pg_provider"], row["pg_tx_id"]):
                        db.set_order_status(int(oid), "refunded")
                        st.success(f"주문 #{oid} 환불 처리 완료")
                        st.rerun()
                except NotImplementedError as e:
                    st.error(str(e))

    with t_users:
        st.dataframe(users, width="stretch", hide_index=True)
        if len(users):
            st.download_button("회원 CSV 다운로드", users.to_csv(index=False).encode("utf-8-sig"), "users.csv", "text/csv")
            st.markdown("**회원 관리**")
            others = users[users["id"] != me["id"]]
            if len(others):
                uid = st.selectbox(
                    "회원 선택", others["id"].tolist(),
                    format_func=lambda i: "#{} {} ({})".format(i, others[others["id"] == i].iloc[0]["email"],
                                                              others[others["id"] == i].iloc[0]["role"]))
                row = others[others["id"] == uid].iloc[0]
                c = st.columns(3)
                if c[0].button("비활성화" if row["is_active"] else "활성화", width="stretch"):
                    db.set_user_active(int(uid), not bool(row["is_active"]))
                    st.rerun()
                if not row["email_verified"] and c[1].button("이메일 인증 처리", width="stretch"):
                    db.set_email_verified(int(uid), True)
                    st.rerun()
                if c[2].button("관리자 해제" if row["role"] == "admin" else "관리자로 지정", width="stretch"):
                    db.set_user_role(int(uid), "user" if row["role"] == "admin" else "admin")
                    st.rerun()

    with t_set:
        with st.form("settings"):
            new_price = st.number_input("건당 가격 (원)", min_value=0, step=100, value=price())
            new_name = st.text_input("서비스 이름", value=service_name())
            cats_on = st.multiselect("노출할 운세 카테고리", list(CATS), default=enabled_cats(),
                                     format_func=lambda k: CATS[k][1])
            has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
            llm = st.toggle("LLM(Claude) 풀이 사용", value=db.get_setting("use_llm", "0") == "1", disabled=not has_key,
                            help="환경변수 ANTHROPIC_API_KEY가 설정되어야 사용할 수 있습니다. 실패 시 기본 풀이로 대체됩니다.")
            if st.form_submit_button("저장", type="primary"):
                db.set_setting("price", str(int(new_price)))
                db.set_setting("service_name", new_name.strip() or "AI 사주")
                db.set_setting("enabled_cats", json.dumps(cats_on))
                db.set_setting("use_llm", "1" if (llm and has_key) else "0")
                st.success("저장했습니다.")
        st.markdown("**시스템 상태**")
        st.write(f"- 데이터 저장소: {db.backend_label()}")
        st.write(f"- 이메일 발송(SMTP): {'✅ 설정됨' if mailer.configured() else '❌ 미설정'}")
        st.write(f"- LLM 키(ANTHROPIC_API_KEY): {'✅ 설정됨' if os.environ.get('ANTHROPIC_API_KEY') else '미설정'}")
        st.write(f"- 앱 버전: {APP_VERSION}")
        if st.button("내 이메일로 테스트 메일 보내기", disabled=not mailer.configured()):
            try:
                mailer.send(me["email"], f"[{service_name()}] 테스트 메일", "이 메일이 보이면 이메일 발송 설정이 정상입니다.")
                st.success(f"{me['email']} 로 테스트 메일을 보냈습니다. 스팸함도 확인해 보세요.")
            except Exception as e:
                st.error(f"발송 실패: {type(e).__name__}: {e}")
        st.markdown("**관리자 비밀번호 변경**")
        with st.form("chpw"):
            npw = st.text_input("새 비밀번호 (8자 이상)", type="password")
            if st.form_submit_button("변경"):
                try:
                    db.change_password(me["id"], npw)
                    st.success("변경했습니다.")
                except ValueError as e:
                    st.error(str(e))


# ---------- 내비게이션 ----------
PAGES["home"] = st.Page(home, title="사주 보기", icon="🔮", url_path="home", default=True)
PAGES["auth"] = st.Page(auth_page, title="로그인 / 회원가입", icon="🔑", url_path="auth")
PAGES["my"] = st.Page(mypage, title="마이페이지", icon="👤", url_path="my")
PAGES["admin"] = st.Page(admin_page, title="관리자", icon="🛠️", url_path="admin")

u = user()
nav = [PAGES["home"]]
if u:
    nav.append(PAGES["my"])
    if u["role"] == "admin":
        nav.append(PAGES["admin"])
else:
    nav.append(PAGES["auth"])

pg = st.navigation(nav)

with st.sidebar:
    if u:
        st.divider()
        st.page_link(PAGES["my"], label=f"{u['name']}님", icon="👤", width="stretch")
        if st.button("로그아웃", width="stretch"):
            st.session_state.pop("user", None)
            st.rerun()
    st.caption(f"v{APP_VERSION}")

pg.run()
