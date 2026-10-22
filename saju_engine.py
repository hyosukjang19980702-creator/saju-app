"""사주 명식(四柱) 계산 엔진.

- 절기·간지(년/월/일/시주) 계산: lunar_python 사용 (입춘/절기 경계 반영)
- 십성·오행·신강/신약 분석: 직접 구현
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta

from lunar_python import Lunar, Solar

STEM_KO = "갑을병정무기경신임계"
STEM_ZH = "甲乙丙丁戊己庚辛壬癸"
BR_KO = "자축인묘진사오미신유술해"
BR_ZH = "子丑寅卯辰巳午未申酉戌亥"
ELEMENTS = ["목", "화", "토", "금", "수"]
EL_COLOR = ["#2e9e5b", "#e0483e", "#c49a1c", "#8a8f98", "#2f6fdb"]

STEM_EL = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
BR_EL = [4, 2, 0, 0, 2, 1, 1, 2, 3, 3, 2, 4]
# 지지의 본기(주된 천간) 인덱스: 자→계, 축→기, 인→갑, 묘→을, 진→무, 사→병, 오→정, 미→기, 신→경, 유→신, 술→무, 해→임
BR_MAIN = [9, 5, 0, 1, 4, 2, 3, 5, 6, 7, 4, 8]

GROUPS = ["비겁", "식상", "재성", "관성", "인성"]
GROUP_OF = {
    "비견": "비겁", "겁재": "비겁", "식신": "식상", "상관": "식상",
    "편재": "재성", "정재": "재성", "편관": "관성", "정관": "관성",
    "편인": "인성", "정인": "인성",
}
LABELS = ["시주", "일주", "월주", "년주"]  # 화면 표시 순서(오른쪽이 년주)


def ten_god(dm: int, t: int) -> str:
    """일간(dm) 기준 천간(t)의 십성."""
    de, te = STEM_EL[dm], STEM_EL[t]
    same = dm % 2 == t % 2
    if te == de:
        return "비견" if same else "겁재"
    if te == (de + 1) % 5:
        return "식신" if same else "상관"
    if te == (de + 2) % 5:
        return "편재" if same else "정재"
    if (te + 2) % 5 == de:
        return "편관" if same else "정관"
    return "편인" if same else "정인"


def _to_solar(y, m, d, hh, mm, calendar, leap):
    if calendar == "음력":
        return Lunar.fromYmdHms(y, -m if leap else m, d, hh, mm, 0).getSolar()
    return Solar.fromYmdHms(y, m, d, hh, mm, 0)


def _pillar(label, gz, dm, is_day=False):
    s, b = STEM_ZH.index(gz[0]), BR_ZH.index(gz[1])
    return {
        "label": label, "stem": s, "br": b,
        "stem_zh": STEM_ZH[s], "stem_ko": STEM_KO[s], "stem_el": STEM_EL[s], "stem_el_ko": ELEMENTS[STEM_EL[s]],
        "br_zh": BR_ZH[b], "br_ko": BR_KO[b], "br_el": BR_EL[b], "br_el_ko": ELEMENTS[BR_EL[b]],
        "stem_tg": "일간(나)" if is_day else ten_god(dm, s),
        "br_tg": ten_god(dm, BR_MAIN[b]),
    }


def chart_key(y, m, d, hour, minute, gender, calendar, leap, adj) -> str:
    raw = f"{y}-{m}-{d}-{hour}-{minute}-{gender}-{calendar}-{leap}-{adj}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def compute_chart(y, m, d, hour=None, minute=0, gender="여성", calendar="양력", leap=False, kst_adjust=False) -> dict:
    known = hour is not None
    hh, mm = (hour, minute) if known else (12, 0)
    solar = _to_solar(y, m, d, hh, mm, calendar, leap)
    if known and kst_adjust:
        t = datetime(solar.getYear(), solar.getMonth(), solar.getDay(), hh, mm) - timedelta(minutes=30)
        solar = Solar.fromYmdHms(t.year, t.month, t.day, t.hour, t.minute, 0)
    ec = solar.getLunar().getEightChar()
    dm = STEM_ZH.index(ec.getDay()[0])

    pillars = [
        _pillar("시주", ec.getTime(), dm) if known else None,
        _pillar("일주", ec.getDay(), dm, is_day=True),
        _pillar("월주", ec.getMonth(), dm),
        _pillar("년주", ec.getYear(), dm),
    ]
    present = [p for p in pillars if p]

    el_count = [0] * 5
    counts = {g: 0 for g in GROUPS}
    for p in present:
        el_count[p["stem_el"]] += 1
        el_count[p["br_el"]] += 1
        if p["label"] != "일주":
            counts[GROUP_OF[p["stem_tg"]]] += 1
        counts[GROUP_OF[p["br_tg"]]] += 1

    month_group = GROUP_OF[pillars[2]["br_tg"]]
    scores = {g: counts[g] + (1.0 if g == month_group else 0.0) for g in GROUPS}  # 월지(득령) 가중
    support = scores["비겁"] + scores["인성"]
    other = scores["식상"] + scores["재성"] + scores["관성"]
    strength = "신강" if support > other + 0.5 else "신약" if support + 0.5 < other else "균형"
    dom = max(GROUPS, key=lambda g: (scores[g], -GROUPS.index(g)))

    today = date.today()
    ty = Solar.fromYmd(today.year, today.month, today.day).getLunar().getEightChar().getYear()
    ts, tb = STEM_ZH.index(ty[0]), BR_ZH.index(ty[1])
    year_luck = {
        "gz_ko": STEM_KO[ts] + BR_KO[tb], "gz_zh": ty,
        "stem_tg": ten_god(dm, ts), "group": GROUP_OF[ten_god(dm, ts)], "year": today.year,
    }

    spouse_group = "재성" if gender == "남성" else "관성"
    return {
        "solar": solar.toYmd(), "known_time": known, "pillars": pillars,
        "day_master": {"ko": STEM_KO[dm], "zh": STEM_ZH[dm], "el": ELEMENTS[STEM_EL[dm]]},
        "el_count": dict(zip(ELEMENTS, el_count)),
        "lacking": [ELEMENTS[i] for i, c in enumerate(el_count) if c == 0],
        "group_counts": counts, "dom_group": dom, "strength": strength,
        "year_luck": year_luck, "spouse_group": spouse_group, "spouse_count": counts[spouse_group],
        "gender": gender,
    }


def today_info(dm_ko: str, d: date | None = None) -> dict:
    """오늘(또는 d)의 일진(日辰)과 일간(dm_ko) 기준 십성."""
    d = d or date.today()
    dm = STEM_KO.index(dm_ko)
    gz = Solar.fromYmd(d.year, d.month, d.day).getLunar().getDayInGanZhi()
    s, b = STEM_ZH.index(gz[0]), BR_ZH.index(gz[1])
    tg = ten_god(dm, s)
    return {"date": d.isoformat(), "gz_ko": STEM_KO[s] + BR_KO[b], "gz_zh": gz, "stem_tg": tg,
            "group": GROUP_OF[tg], "br_tg": ten_god(dm, BR_MAIN[b])}
