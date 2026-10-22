"""운세별 인물의 대화 형식 풀이 생성.

기본 풀이 문구(interpret.py)를 인물의 사극 말투로 바꾸고, 여러 개의 말풍선(대화)으로 나눕니다.
"""
from __future__ import annotations

import html
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import characters as ch
import interpret as itp
import saju_engine as se

SEP = "\n\n<!--msg-->\n\n"  # 저장된 풀이에서 말풍선을 나누는 구분자

DEFAULT_PRICES = {"love": 2900, "wealth": 2900, "career": 2900, "commute": 990}
DAILY = {"commute"}  # 날짜에 따라 달라지는 운세(같은 날 재열람은 무료, 다음 날은 새로 결제)

LOCKED = {
    "love": ["타고난 성향", "마음의 흐름", "올해의 인연운", "주의할 점", "실천 조언", "오행 보완 팁"],
    "wealth": ["타고난 재물 그릇", "돈이 모이는 길", "올해의 재물운", "주의할 점", "실천 조언", "오행 보완 팁"],
    "career": ["타고난 재목", "맞는 길", "올해의 관운", "주의할 점", "실천 조언", "오행 보완 팁"],
    "commute": ["출근길 조언", "업무 흐름", "주의할 점", "오늘의 행운 소품"],
}

# (…ㅂ니다 어미, …습니다 어미, …세요 어미)
STYLES = {"hao": ("오", "소", "시오"), "okay": ("옵니다", "사옵니다", "소서"), "oeda": ("외다", "소이다", "시구려")}


def today_kst() -> date:
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


def order_key(chart_key: str, cat: str, today: date | None = None) -> str:
    """주문 중복 확인용 키. 일일 운세는 날짜가 바뀌면 새 상품."""
    return f"{chart_key}:{(today or today_kst()).isoformat()}" if cat in DAILY else chart_key


def sageuk(text: str, style: str) -> str:
    """합니다체 문장을 사극 말투로 바꿉니다."""
    bsuf, seub, seyo = STYLES[style]
    t = text.replace("습니다", "")

    def f(m):
        c = m.group(1)
        code = ord(c) - 0xAC00
        if 0 <= code < 11172 and code % 28 == 17:  # 받침 ㅂ 제거 + 어미
            return chr(ord(c) - 17) + bsuf
        return m.group(0)

    t = re.sub(r"([가-힣])니다", f, t)
    return t.replace("", seub).replace("세요", seyo)


def md_lite(text: str) -> str:
    """**굵게**, 줄바꿈, '- ' 목록만 지원하는 가벼운 변환(HTML)."""
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    lines = [("• " + ln[2:]) if ln.startswith("- ") else ln for ln in t.split("\n")]
    return "<br>".join(lines)


EL_COLOR = {"목": "초록·청록 계열", "화": "붉은·주황 계열", "토": "노랑·베이지 계열", "금": "흰색·은색 계열", "수": "남색·검정 계열"}
EL_DIR = {"목": "동쪽", "화": "남쪽", "토": "가까운 중앙", "금": "서쪽", "수": "북쪽"}

COMMUTE = {
    "비겁": ("주변과 힘을 겨루기 쉬운 날",
           "오늘은 나와 같은 기운이 밀려와 자신감이 오르지만 고집도 함께 세지는 날입니다.",
           "대중교통에서 서두르다 부딪히거나 작은 말다툼이 생기기 쉬우니 여유 있게 나서세요.",
           "동료와 의견이 갈릴 수 있으니 주장하기 전에 한 번 더 들어 주면 일이 매끄럽습니다.",
           "지출 충동과 경쟁심을 조심하세요."),
    "식상": ("말과 아이디어가 빛나는 날",
           "표현력과 센스가 올라가는 날입니다.",
           "이동 중에 떠오르는 생각을 메모해 두세요. 좋은 아이디어가 나올 수 있습니다.",
           "회의·발표·기획처럼 말하고 보여 주는 일에 유리합니다.",
           "말이 앞서 실수하기 쉬우니 메신저와 메일은 보내기 전에 한 번 더 읽으세요."),
    "재성": ("성과와 실속이 따르는 날",
           "눈에 보이는 결과와 실리를 챙기기 좋은 날입니다.",
           "평소보다 조금 일찍 나서면 좋은 기회와 연락이 먼저 닿습니다.",
           "계약·정산·영업처럼 숫자와 결과가 걸린 일에 힘이 실립니다.",
           "충동구매와 욕심을 부리면 새기 쉽습니다."),
    "관성": ("책임과 평가가 따르는 날",
           "규칙과 책임이 무겁게 느껴질 수 있는 날입니다.",
           "시간 여유를 두고 익숙한 길로 가세요. 지각이나 돌발 상황을 피하는 편이 이롭습니다.",
           "상사의 시선이나 마감 압박이 있을 수 있으니 우선순위를 먼저 정리해 두면 편합니다.",
           "무리하게 떠안지 말고 점심 후 잠깐이라도 쉬어 가세요."),
    "인성": ("배움과 도움이 찾아오는 날",
           "조언과 귀인의 기운이 드는 날입니다.",
           "출근길에 책이나 강의를 들으면 평소보다 머릿속에 잘 남습니다.",
           "문서·자격·학습처럼 차분히 쌓는 일에 유리하고, 선배의 조언을 구하면 길이 열립니다.",
           "생각만 길어지고 실행이 늦어질 수 있으니 작은 것부터 먼저 끝내세요."),
}


def _who(name: str) -> str:
    return f"{name.strip()}님" if name and name.strip() else "그대"


def _fmt_head(p: dict, **kw) -> str:
    return p["head"].format(**kw)


def build_messages(chart: dict, cat: str, name: str = "", today: date | None = None) -> list[str]:
    p = ch.PERSONAS[cat]
    st_ = p["style"]
    S = lambda s: sageuk(s, st_)  # noqa: E731
    who = _who(name)
    L = p["leads"]
    dm = chart["day_master"]

    if cat == "commute":
        ti = se.today_info(dm["ko"], today or today_kst())
        head, body, commute, work, caution = COMMUTE[ti["group"]]
        helpful = chart["lacking"][0] if chart["lacking"] else itp_helpful(dm["el"])
        greet = p["greet"].format(who=who) + "\n\n" + _fmt_head(p, gz=ti["gz_ko"], head=head)
        lucky = S(f"오늘 곁에 두면 좋은 기운은 **{helpful}**입니다. {EL_COLOR[helpful]} 소품이나 옷, {EL_DIR[helpful]} 방향의 자리가 도움이 됩니다.")
        return [
            greet,
            f"{L['nature']}\n\n{S(body)}",
            f"{L['commute']}\n\n{S(commute)}",
            f"{L['work']}\n\n{S(work)}",
            f"{L['caution']}\n\n{S(caution)}",
            f"{L['lucky']}\n\n{lucky}",
            p["outro"],
        ]

    head, body, caution, advice = itp.T[cat][chart["dom_group"]]
    yl = chart["year_luck"]
    extra = ("\n\n" + S(itp._spouse_line(chart))) if cat == "love" else ""
    lack = chart["lacking"]
    tip = ("\n".join(f"- **{e}**: {itp.EL_TIP[e]}" for e in lack) if lack
           else S("오행이 고르게 분포해 특별히 부족한 기운이 없습니다."))
    nature = (f"{L['nature']}\n\n" +
              S(f"일간은 **{dm['ko']}({dm['zh']}, {dm['el']})**입니다. {itp.DAY_MASTER[dm['el']]}") + "\n" +
              S(f"사주의 힘은 **{chart['strength']}** 쪽입니다. {itp.STRENGTH[chart['strength']]}"))
    return [
        p["greet"].format(who=who) + "\n\n" + _fmt_head(p, head=head),
        nature,
        f"{L['detail']}\n\n{S(body)}{extra}",
        f"{L['year']}\n\n" + S(f"올해는 **{yl['gz_ko']}년({yl['stem_tg']} 기운)**입니다. {itp.YEAR[cat][yl['group']]}"),
        f"{L['caution']}\n\n{S(caution)}",
        f"{L['advice']}\n\n{S(advice)}",
        f"{L['tip']}\n\n{tip}",
        p["outro"],
    ]


def itp_helpful(dm_el: str) -> str:
    els = se.ELEMENTS
    return els[(els.index(dm_el) - 1) % 5]  # 일간을 생(生)해 주는 오행


def preview_messages(chart: dict, cat: str, name: str = "", today: date | None = None) -> list[str]:
    """무료로 보여 주는 대화(첫 인사 + 한 줄 풀이)."""
    msgs = build_messages(chart, cat, name, today)
    if cat == "commute":
        return msgs[:2]
    teaser = itp.preview(chart, cat)["teaser"]
    return [msgs[0], sageuk(teaser, ch.PERSONAS[cat]["style"]) + " …"]


def full_content(chart: dict, cat: str, name: str = "", today: date | None = None) -> str:
    return SEP.join(build_messages(chart, cat, name, today))


def bubbles_html(cat: str, msgs: list[str]) -> str:
    p = ch.PERSONAS[cat]
    ava = ch.avatar_html(cat, 48)
    rows = []
    for i, m in enumerate(msgs):
        who = (f'<div class="chat-name">{html.escape(p["name"])}</div>') if i == 0 else ""
        rows.append(f'<div class="chat-row">{ava}<div class="chat-col">{who}<div class="chat-bubble">{md_lite(m)}</div></div></div>')
    return "".join(rows)


def content_to_msgs(content: str) -> list[str] | None:
    """저장된 풀이가 대화 형식이면 말풍선 목록, 예전 형식이면 None."""
    return content.split(SEP) if content and "<!--msg-->" in content else None
