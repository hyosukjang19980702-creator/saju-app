"""AI 사주 서비스 (Streamlit).  실행: streamlit run app.py"""
import json
import logging
import os
from datetime import date, time
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

import db
import characters as ch
import fortune
import interpret as itp
import legal
import mailer
import payments
import saju_engine as se
import theme

st.set_page_config(page_title="천상운명", page_icon="🌙", layout="centered")
st.markdown(theme.CSS, unsafe_allow_html=True)


@st.cache_resource
def _init_db():
    db.init_db()
    return True


_init_db()

APP_VERSION = "0.6.1"
CATS = itp.CATEGORIES
PAGES: dict = {}


# ---------- 공통 헬퍼 ----------
def user():
    return st.session_state.get("user")


def won(n) -> str:
    return f"{int(n):,}원"


def price_for(cat: str) -> int:
    default = fortune.DEFAULT_PRICES.get(cat, 2900)
    try:
        return int(db.get_setting(f"price_{cat}", str(default)))
    except ValueError:
        return default


def service_name() -> str:
    name = db.get_setting("service_name", "천상운명")
    return "천상운명" if name in ("", "AI 사주") else name


def biz(key: str) -> str:
    """사업자 정보: 관리자가 저장한 값 우선, 없으면 기본값(legal.BUSINESS_DEFAULTS)."""
    return db.get_setting(key, "").strip() or legal.BUSINESS_DEFAULTS.get(key, "")


def doc_text(dk: str, default: str) -> str:
    txt = db.get_setting(f"doc_{dk}", default)
    return txt.replace("{service}", service_name()).replace("{phone}", biz("biz_phone") or "고객센터")


def enabled_cats() -> list:
    try:
        keys = json.loads(db.get_setting("enabled_cats_v2", json.dumps(list(CATS))))
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


def render_content(cat: str, content: str):
    """저장된 풀이를 대화(말풍선) 형식으로, 예전 형식이면 일반 글로 표시."""
    msgs = fortune.content_to_msgs(content)
    if msgs and cat in ch.PERSONAS:
        st.markdown(fortune.bubbles_html(cat, msgs), unsafe_allow_html=True)
    else:
        st.markdown(content or "")


# ---------- 결제 ----------
def public_url() -> str:
    """결제 후 돌아올 서비스 주소. Secrets의 PUBLIC_URL 우선, 없으면 접속 주소로 추정."""
    u = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
    if u:
        return u
    try:
        h = st.context.headers
        host = h.get("Host") or h.get("host")
        if host:
            proto = h.get("X-Forwarded-Proto") or ("http" if host.startswith(("localhost", "127.")) else "https")
            return f"{proto.split(',')[0].strip()}://{host}"
    except Exception:
        pass
    return ""


def show_flash():
    flash = st.session_state.pop("flash", None)
    if flash:
        lvl, msg = flash if isinstance(flash, tuple) else ("success", flash)
        getattr(st, lvl)(msg)


@st.dialog("상세 풀이 결제")
def pay_dialog(cat: str):
    ctx, u = st.session_state["ctx"], user()
    icon, label = CATS[cat]
    amount = price_for(cat)
    okey = fortune.order_key(ctx["key"], cat)
    st.markdown(f"**{icon} {label}** · {ch.PERSONAS[cat]['name']}의 풀이 · **{won(amount)}** (1건)")
    if not u:
        st.caption("비회원으로 결제합니다. 결제 후 화면에 표시되는 **주문 열람 링크**를 저장해 두시면 풀이를 다시 볼 수 있어요.")
    if payments.mode() == "mock":
        st.warning("테스트 결제 모드입니다. 실제로 청구되지 않습니다.")
    elif not payments.is_live():
        st.info("결제 테스트 모드입니다(토스페이먼츠 테스트 키). 실제로 청구되지 않습니다.")

    with st.container(border=True):
        st.markdown(legal.REFUND_SUMMARY.replace("{phone}", biz("biz_phone") or "고객센터"))
        st.caption("전체 내용은 화면 하단의 '환불정책'에서 확인하실 수 있습니다.")
    agree = st.checkbox("위 환불 안내를 확인했으며, 디지털 콘텐츠 제공 개시 후 청약철회가 제한됨에 동의합니다.")

    def new_order():
        uid = u["id"] if u else db.create_guest_user()
        payload = json.dumps({**ctx["params"], "name": ctx["name"]}, ensure_ascii=False)
        return db.create_pending_order(uid, okey, cat, ctx["summary"], amount, payload)

    if payments.mode() == "mock":
        if st.button("결제하기", type="primary", disabled=not agree, width="stretch"):
            with st.spinner("결제 및 풀이 생성 중..."):
                order_no, token = new_order()
                ok, tx, provider = payments.charge(u or {}, amount, f"{label} 풀이")
                if ok:
                    content = fortune.full_content(ctx["chart"], cat, ctx["name"])
                    db.complete_order(order_no, tx, provider, content)
                    o = db.get_order_by_no(order_no)
                    db.log_event("paid", o["user_id"] if u else None, cat)
                    if not u:
                        st.session_state["guest_view"] = {"no": order_no, "t": token}
            st.rerun()
        return

    base = public_url()
    if not base:
        st.error("서비스 주소(PUBLIC_URL)가 설정되지 않아 결제를 진행할 수 없습니다. 운영자에게 문의해 주세요.")
        return
    key = f"pay_url_{okey}_{cat}"
    if st.button("결제 진행하기", type="primary", disabled=not agree, width="stretch"):
        order_no, token = new_order()
        params = {
            "ck": payments.client_key(), "orderId": order_no, "amount": amount, "orderName": f"{label} 풀이",
            "successUrl": f"{base}/?pay=success&t={token}", "failUrl": f"{base}/?pay=fail",
        }
        if u:
            params.update({"email": u["email"], "name": u["name"]})
        st.session_state[key] = f"{base}/app/static/checkout.html?{urlencode(params)}"
    if st.session_state.get(key):
        st.link_button("💳 결제창 열기", st.session_state[key], type="primary", width="stretch")
        st.caption("결제창은 새 탭에서 열립니다. 결제가 끝나면 자동으로 돌아와 풀이가 열려요.")


def guest_result_block():
    """비회원 결제 후(또는 열람 링크로 접속 시) 풀이를 보여줍니다."""
    gv = st.session_state.get("guest_view")
    if not gv:
        return
    o = db.get_guest_order(gv["no"], gv["t"])
    if not o:
        return
    icon, label = CATS.get(o["category"], ("", o["category"]))
    st.success(f"{icon} {label} 풀이가 열렸어요. (주문번호 {o['order_no']})")
    with st.expander("📖 전체 풀이 보기", expanded=True):
        render_content(o["category"], o["content"])
    base = public_url()
    if base:
        st.markdown("**🔗 주문 열람 링크** — 저장해 두면 언제든 이 풀이를 다시 볼 수 있어요. (타인에게 공유하지 마세요)")
        st.code(f"{base}/?view={o['order_no']}&t={gv['t']}", language=None)
    st.caption(f"환불·문의는 주문번호를 알려 주세요. 고객센터 {biz('biz_phone') or ''}")
    st.divider()


def handle_payment_return():
    """토스페이먼츠 결제 후 돌아온 요청 처리: 금액 검증 → 서버 승인 → 풀이 생성 → 주문 완료."""
    qp = st.query_params
    if qp.get("view"):  # 비회원 주문 열람 링크
        st.session_state["guest_view"] = {"no": qp.get("view", ""), "t": qp.get("t", "")}
        st.query_params.clear()
        return
    kind = qp.get("pay")
    if kind not in ("success", "fail"):
        return
    order_no = qp.get("orderId", "")
    params = dict(qp)
    st.query_params.clear()

    def done(level, msg, goto=False):
        st.session_state["flash"] = (level, msg)
        if goto:
            st.session_state["goto_my"] = True

    order = db.get_order_by_no(order_no)
    if not order:
        return done("error", "주문 정보를 찾을 수 없습니다. 문제가 계속되면 고객센터로 문의해 주세요.")

    # 결제 후 돌아온 브라우저를 일회성 토큰으로 본인 확인 → 로그인 복원
    uid = db.consume_return_token(order_no, params.get("t", ""))
    if uid and not user():
        restored = db.get_active_user(uid)
        if restored:
            st.session_state["user"] = restored

    if kind == "fail":
        db.fail_order(order_no)
        return done("error", f"결제가 완료되지 않았습니다. {params.get('message', '')} (청구되지 않았습니다.)")

    guest = db.is_guest_user(order["user_id"])
    if order["status"] == "paid":
        if guest:
            st.session_state["guest_view"] = {"no": order_no, "t": params.get("t", "")}
            return done("success", "이미 처리된 결제입니다. 아래에서 풀이를 확인하세요.")
        return done("success", "이미 처리된 결제입니다. 마이페이지에서 풀이를 확인하세요.", goto=True)
    if order["status"] != "pending":
        return done("error", "처리할 수 없는 주문입니다. 고객센터로 문의해 주세요.")
    try:
        amount = int(params.get("amount", "0"))
    except ValueError:
        amount = 0
    if amount != order["amount"]:  # 금액 위·변조 방지: 서버에 저장된 금액과 다르면 승인하지 않음
        db.fail_order(order_no)
        return done("error", "결제 금액이 주문과 일치하지 않아 승인하지 않았습니다. 청구되지 않습니다.")
    try:
        data = payments.confirm(params.get("paymentKey", ""), order_no, order["amount"])
    except payments.PaymentError as e:
        if e.code == "NETWORK":  # 승인 여부가 불확실 → 실패 처리하지 않고 대기 유지
            return done("warning", f"결제 확인 중 통신 오류가 발생했습니다. 풀이가 열리지 않으면 주문번호 {order_no} 로 문의해 주세요.")
        db.fail_order(order_no)
        return done("error", f"결제 승인에 실패했습니다. ({e.code}) {e.message}")

    try:
        p = json.loads(order["payload"] or "{}")
        chart = se.compute_chart(p["y"], p["m"], p["d"], p["hour"], p["minute"], p["gender"], p["calendar"], p["leap"], p["adj"])
        content = fortune.full_content(chart, order["category"], p.get("name", ""))
    except Exception:
        logging.getLogger("saju.pay").exception("content generation failed for %s", order_no)
        content = "풀이 생성 중 문제가 발생했습니다. 고객센터에 주문번호 " + order_no + " 로 문의해 주세요."
    db.complete_order(order_no, data["paymentKey"], "toss", content)
    db.log_event("paid", None if guest else order["user_id"], order["category"])
    if guest:
        st.session_state["guest_view"] = {"no": order_no, "t": params.get("t", "")}
        done("success", "결제가 완료되었습니다! 아래에서 풀이를 확인하세요.")
    elif user():
        done("success", "결제가 완료되었습니다! 아래에서 풀이를 확인하세요.", goto=True)
    else:
        done("success", "결제가 완료되었습니다! 로그인하면 마이페이지에서 풀이를 볼 수 있어요.")


# ---------- 홈 ----------
def pick_cards():
    st.markdown('<div id="pick"></div>', unsafe_allow_html=True)
    st.subheader("어떤 운을 보고 싶으신가요?")
    st.caption("보고 싶은 운세를 고르면, 그 일에 밝은 인물이 대화하듯 풀이해 드려요. 요약은 무료입니다.")
    cats = enabled_cats()
    for i in range(0, len(cats), 2):
        cols = st.columns(2)
        for col, cat in zip(cols, cats[i:i + 2]):
            p = ch.PERSONAS[cat]
            with col.container(border=True):
                st.markdown(
                    ch.portrait_html(cat, "4 / 3")
                    + f'<div class="pname">{CATS[cat][1]}</div><div class="ptitle">{p["name"]} · {p["title"]}</div>'
                    + f'<div class="ptag">{p["tagline"]}</div><span class="price">{won(price_for(cat))}</span> <span class="ptitle">요약 무료</span>',
                    unsafe_allow_html=True)
                if st.button("이분께 묻기  →", key=f"pick_{cat}", type="primary", width="stretch"):
                    st.session_state["cat_sel"] = cat
                    st.rerun()


def fortune_view(ctx, cat):
    p = ch.PERSONAS[cat]
    icon, label = CATS[cat]
    u = user()
    okey = fortune.order_key(ctx["key"], cat)
    st.subheader(f"{icon} {label} · {p['name']}")
    if cat in fortune.DAILY:
        st.caption(f"{fortune.today_kst().strftime('%Y년 %m월 %d일')} 하루의 운세예요. 오늘은 다시 볼 수 있고, 내일은 새로 풀이합니다.")
    order = db.find_order(u["id"], okey, cat) if u else None
    if order:
        render_content(cat, order["content"])
        return
    msgs = fortune.preview_messages(ctx["chart"], cat, ctx["name"])
    st.markdown(fortune.bubbles_html(cat, msgs), unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("🔒 **이어서 들려주실 이야기**")
        st.markdown(" · ".join(fortune.LOCKED[cat]))
        if st.button(f"🔓 {won(price_for(cat))} 결제하고 이어서 듣기", key=f"pay_{cat}", type="primary", width="stretch"):
            db.log_event("pay_open", (u or {}).get("id"), cat)
            pay_dialog(cat)
        if not u:
            st.caption("회원가입 없이 카드로 바로 결제할 수 있어요. 회원이면 구매내역에서 풀이를 다시 볼 수 있습니다.")


def home():
    show_flash()
    guest_result_block()
    cats = enabled_cats()
    sel = st.session_state.get("cat_sel")
    if sel not in cats:
        sel = None

    if not sel:
        st.markdown(theme.hero_html(service_name()), unsafe_allow_html=True)
        pick_cards()
        st.caption(itp.DISCLAIMER)
        return

    if st.button("← 다른 운세 고르기", key="back_main"):
        st.session_state["cat_sel"] = None
        st.rerun()
    p = ch.PERSONAS[sel]
    c1, c2 = st.columns([1, 6])
    c1.markdown(ch.avatar_html(sel, 64), unsafe_allow_html=True)
    c2.markdown(f'<div class="pname" style="margin-top:0">{p["name"]}</div><div class="ptitle">{p["title"]}</div>'
                f'<div class="ptag">{p["tagline"]}</div>', unsafe_allow_html=True)

    ctx = st.session_state.get("ctx")
    with st.expander("생년월일 입력" if not ctx else "생년월일 다시 입력", expanded=not ctx):
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
            ctx = st.session_state["ctx"] = {
                "chart": chart, "name": name.strip(),
                "key": se.chart_key(bd.year, bd.month, bd.day, hour, minute, gender, cal, leap, adj),
                "summary": f"{bd.isoformat()} {tstr} {cal} {gender}",
                "params": {"y": bd.year, "m": bd.month, "d": bd.day, "hour": hour, "minute": minute,
                           "gender": gender, "calendar": cal, "leap": leap, "adj": adj},
            }
            db.log_event("chart", (user() or {}).get("id"))
            st.rerun()

    if not ctx:
        st.caption(itp.DISCLAIMER)
        return
    chart = ctx["chart"]
    with st.expander("내 사주 명식 보기"):
        st.caption(f"양력 환산 {chart['solar']} · 일간 {chart['day_master']['ko']}({chart['day_master']['zh']}, {chart['day_master']['el']}) · {chart['strength']}")
        cols = st.columns(4)
        for col, pil, lab in zip(cols, chart["pillars"], se.LABELS):
            col.markdown(pillar_html(lab, pil), unsafe_allow_html=True)
        st.bar_chart(pd.DataFrame({"개수": chart["el_count"]}), height=180)
    st.divider()
    fortune_view(ctx, sel)
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
            logging.getLogger("saju.mail").warning("verification mail failed: %s: %s", type(e).__name__, e)
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
    show_flash()
    t_orders, t_id, t_pw, t_out = st.tabs(["구매내역", "아이디", "비밀번호", "회원탈퇴"])

    with t_orders:
        orders = [o for o in db.user_orders(u["id"]) if o["status"] in ("paid", "refunded")]
        if not orders:
            st.info("아직 구매한 풀이가 없어요. 사주 보기에서 시작해 보세요.")
        for o in orders:
            icon, label = CATS.get(o["category"], ("", o["category"]))
            badge = "" if o["status"] == "paid" else " (환불됨)"
            with st.expander(f"{icon} {label} · {o['birth_summary']} · {won(o['amount'])} · {o['created_at']}{badge}"):
                if o["status"] == "paid":
                    render_content(o["category"], o["content"])
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
    if payments.is_live():
        st.success("현재 **실결제 모드**입니다. 고객 결제가 실제로 청구됩니다.")
    elif payments.mode() == "mock":
        st.info("현재 결제는 **테스트(mock)** 입니다. 고객에게 청구되지 않습니다. 토스페이먼츠 키를 설정하면 실제 결제 연동이 시작됩니다.")
    else:
        st.info("현재 토스페이먼츠 **테스트 키**로 동작 중입니다. 실제 청구는 없습니다. 계약 후 live 키로 바꾸면 실결제가 됩니다.")
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
                except (NotImplementedError, payments.PaymentError) as e:
                    st.error(f"환불 실패: {e}")

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
            new_prices = {c: st.number_input(f"{CATS[c][1]} 가격 (원)", min_value=0, step=100, value=price_for(c), key=f"pr_{c}") for c in CATS}
            new_name = st.text_input("서비스 이름", value=service_name())
            cats_on = st.multiselect("노출할 운세 카테고리", list(CATS), default=enabled_cats(),
                                     format_func=lambda k: CATS[k][1])
            has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
            llm = st.toggle("LLM(Claude) 풀이 사용", value=db.get_setting("use_llm", "0") == "1", disabled=not has_key,
                            help="환경변수 ANTHROPIC_API_KEY가 설정되어야 사용할 수 있습니다. 실패 시 기본 풀이로 대체됩니다.")
            if st.form_submit_button("저장", type="primary"):
                for c, v in new_prices.items():
                    db.set_setting(f"price_{c}", str(int(v)))
                db.set_setting("service_name", new_name.strip() or "AI 사주")
                db.set_setting("enabled_cats_v2", json.dumps(cats_on))
                db.set_setting("use_llm", "1" if (llm and has_key) else "0")
                st.success("저장했습니다.")
        st.markdown("**사업자 정보** (결제사 심사·전자상거래법상 사이트 하단에 표시)")
        with st.form("biz"):
            vals = {k: st.text_input(lab, value=biz(k)) for k, lab in legal.BUSINESS_FIELDS}
            if st.form_submit_button("사업자 정보 저장"):
                for k, v in vals.items():
                    db.set_setting(k, v.strip())
                st.success("저장했습니다.")
        st.markdown("**약관·정책 문서** (초안입니다. 오픈 전 반드시 검토·수정하세요)")
        for dk, (dlabel, default) in legal.DOCS.items():
            with st.expander(dlabel):
                with st.form(f"doc_{dk}"):
                    txt = st.text_area("내용(마크다운)", value=db.get_setting(f"doc_{dk}", default),
                                       height=300, label_visibility="collapsed")
                    if st.form_submit_button(f"{dlabel} 저장"):
                        db.set_setting(f"doc_{dk}", txt)
                        st.success("저장했습니다.")
        st.markdown("**시스템 상태**")
        st.write(f"- 데이터 저장소: {db.backend_label()}")
        st.write(f"- 이메일 발송(SMTP): {'✅ 설정됨' if mailer.configured() else '❌ 미설정'}")
        st.write(f"- LLM 키(ANTHROPIC_API_KEY): {'✅ 설정됨' if os.environ.get('ANTHROPIC_API_KEY') else '미설정'}")
        st.write(f"- 결제: {payments.mode_label()}")
        if payments.mode() == "toss":
            st.write(f"- 서비스 주소(PUBLIC_URL): {public_url() or '❌ 미설정'}")
        st.write(f"- 앱 버전: {APP_VERSION}")
        if st.button("내 이메일로 테스트 메일 보내기", disabled=not mailer.configured()):
            try:
                mailer.send(me["email"], f"[{service_name()}] 테스트 메일", "이 메일이 보이면 이메일 발송 설정이 정상입니다.")
                st.success(f"{me['email']} 로 테스트 메일을 보냈습니다. 스팸함도 확인해 보세요.")
            except Exception as e:
                st.error(f"발송 실패 — {mailer.explain(e)}")
        st.markdown("**관리자 비밀번호 변경**")
        with st.form("chpw"):
            npw = st.text_input("새 비밀번호 (8자 이상)", type="password")
            if st.form_submit_button("변경"):
                try:
                    db.change_password(me["id"], npw)
                    st.success("변경했습니다.")
                except ValueError as e:
                    st.error(str(e))


# ---------- 약관·정책 / 푸터 ----------
def legal_page():
    st.title("📄 약관 · 정책")
    tabs = st.tabs([lab for lab, _ in legal.DOCS.values()])
    for tab, (dk, (dlabel, default)) in zip(tabs, legal.DOCS.items()):
        with tab:
            st.markdown(doc_text(dk, default))
    info = {k: biz(k) for k, _ in legal.BUSINESS_FIELDS}
    if any(info.values()):
        st.divider()
        st.markdown("**사업자 정보**")
        for k, lab in legal.BUSINESS_FIELDS:
            if info[k]:
                st.write(f"- {lab}: {info[k]}")


def footer():
    info = {k: biz(k) for k, _ in legal.BUSINESS_FIELDS}
    st.divider()
    names = dict(legal.BUSINESS_FIELDS)
    parts = [f"{names[k]} {v}" for k, v in info.items() if v]
    if parts:
        st.caption(" | ".join(parts))
    st.page_link(PAGES["legal"], label="이용약관 · 환불정책 · 개인정보처리방침", icon="📄")


# ---------- 내비게이션 ----------
PAGES["home"] = st.Page(home, title="사주 보기", icon="🔮", url_path="home", default=True)
PAGES["auth"] = st.Page(auth_page, title="로그인 / 회원가입", icon="🔑", url_path="auth")
PAGES["my"] = st.Page(mypage, title="마이페이지", icon="👤", url_path="my")
PAGES["admin"] = st.Page(admin_page, title="관리자", icon="🛠️", url_path="admin")
PAGES["legal"] = st.Page(legal_page, title="약관·정책", icon="📄", url_path="legal")

handle_payment_return()  # 결제창에서 돌아온 경우 처리(로그인 복원 포함)

u = user()
nav = [PAGES["home"], PAGES["legal"]]
if u:
    nav.append(PAGES["my"])
    if u["role"] == "admin":
        nav.append(PAGES["admin"])
else:
    nav.append(PAGES["auth"])

pg = st.navigation(nav, position="hidden")  # 기본 메뉴는 숨기고 아래에서 직접 구성
if u and st.session_state.pop("goto_my", False):
    st.switch_page(PAGES["my"])

with st.sidebar:
    if st.button("🔮 사주 보기", key="side_home", width="stretch"):
        st.session_state["cat_sel"] = None  # 운세 선택 화면(메인)으로
        st.switch_page(PAGES["home"])
    if not u:
        st.page_link(PAGES["auth"], label="로그인 / 회원가입", icon="🔑", width="stretch")
    elif u["role"] == "admin":
        st.page_link(PAGES["admin"], label="관리자", icon="🛠️", width="stretch")
    if u:
        st.divider()
        st.page_link(PAGES["my"], label=f"{u['name']}님", icon="👤", width="stretch")  # 누르면 마이페이지
        if st.button("로그아웃", width="stretch"):
            st.session_state.pop("user", None)
            st.rerun()
    st.caption(f"v{APP_VERSION}")

pg.run()
footer()
