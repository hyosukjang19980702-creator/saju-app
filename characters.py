"""운세별 인물(페르소나) 정의와 초상화.

- 초상화는 static/characters/<운세키>.png|jpg|jpeg|webp 파일이 있으면 그 이미지를 사용합니다.
  (love / wealth / career / commute — AI 이미지 생성 도구로 만든 그림을 이 이름으로 올리면 자동 적용)
- 파일이 없으면 아래의 임시 일러스트(SVG)를 보여 줍니다.
"""
from __future__ import annotations

import base64
import io
from functools import lru_cache
from pathlib import Path

IMG_DIR = Path(__file__).parent / "static" / "characters"
EXTS = ("png", "jpg", "jpeg", "webp")

# style: 말투(하오체 / 하옵니다체 / 하외다체)  — fortune.sageuk 참고
PERSONAS = {
    "love": {
        "name": "연화 후궁", "title": "궁궐 깊은 곳의 연심 점사", "emoji": "🌸", "style": "okay",
        "tagline": "말 못 할 마음, 그 한 사람과의 인연을 살펴 드리옵니다.",
        "greet": "{who}, 이 깊은 궁까지 먼 걸음 하셨사옵니다. 연꽃 등불 아래서 그대의 인연을 찬찬히 살피겠사옵니다.",
        "head": "그대의 연심은 **{head}**이라 보이옵니다.",
        "leads": {
            "nature": "먼저 그대의 타고난 결부터 보겠사옵니다.",
            "detail": "이제 마음의 흐름을 말씀드리겠사옵니다.",
            "year": "올해 인연의 기운은 이러하옵니다.",
            "caution": "다만 조심하실 것이 있사옵니다.",
            "advice": "마음을 다하실 방도를 일러 드리겠사옵니다.",
            "tip": "부족한 기운은 이렇게 채워 보시옵소서.",
        },
        "outro": "인연은 하늘이 닿게 하되 마음은 사람이 여는 것이옵니다. 부디 고운 인연 맺으시옵소서.",
    },
    "wealth": {
        "name": "송상 대행수 서만금", "title": "송도 객주의 대행수", "emoji": "💰", "style": "oeda",
        "tagline": "돈이 들고나는 길목을 짚어 드리리다.",
        "greet": "{who}, 잘 오셨소이다. 평생 장사판에서 돈의 흐름을 읽어 온 이 사람이 재물운을 살펴 드리리다.",
        "head": "그대의 재물운은 **{head}**이외다.",
        "leads": {
            "nature": "먼저 타고난 재물 그릇부터 보리다.",
            "detail": "돈이 모이는 길을 말씀드리리다.",
            "year": "올해 재물의 바람은 이러하외다.",
            "caution": "이것만은 조심하시구려.",
            "advice": "이렇게 해 보시구려.",
            "tip": "부족한 기운은 이리 채우시구려.",
        },
        "outro": "재물은 모으는 것보다 지키는 것이 어렵소이다. 부디 큰 부자 되시구려.",
    },
    "career": {
        "name": "이조판서 강태허", "title": "인재를 고르는 이조의 수장", "emoji": "📜", "style": "hao",
        "tagline": "그대의 재목이 어느 자리에 쓰일지 가려 주겠소.",
        "greet": "{who}, 어서 오시오. 이조에서 숱한 인재를 가려 본 내 눈으로 그대의 직운을 살펴보겠소.",
        "head": "그대의 직운은 **{head}**이라 읽히오.",
        "leads": {
            "nature": "먼저 타고난 재목을 보겠소.",
            "detail": "이제 어느 길이 맞는지 말하겠소.",
            "year": "올해 관운의 흐름은 이러하오.",
            "caution": "조심할 일이 있소.",
            "advice": "이렇게 해 보시오.",
            "tip": "부족한 기운은 이리 채우시오.",
        },
        "outro": "재목은 쓰임을 만나야 빛나는 법이오. 때를 놓치지 말고 나아가시오.",
    },
    "commute": {
        "name": "집현전 학사 윤서", "title": "집현전의 젊은 학사", "emoji": "🏯", "style": "hao",
        "tagline": "오늘 하루 출근길의 기운을 미리 읽어 드리겠소.",
        "greet": "{who}, 이른 걸음이시오. 집현전에서 밤새 천문과 역서를 살피던 내가 오늘 하루의 기운을 일러 드리겠소.",
        "head": "오늘은 **{gz}일**, 그대에게는 **{head}**이오.",
        "leads": {
            "nature": "오늘 하루의 기운부터 말하겠소.",
            "commute": "출근길에는 이리하시오.",
            "work": "일터에서는 이러하오.",
            "caution": "조심할 일이 있소.",
            "lucky": "오늘 곁에 둘 만한 것을 알려 드리겠소.",
        },
        "outro": "하루는 길어도 마음 하나 다잡으면 순탄하오. 평안히 다녀오시오.",
    },
}

_SKIN, _INK = "#f0d5b0", "#2a1f16"


def _face(cx=100, cy=112):
    return (f'<ellipse cx="{cx}" cy="{cy}" rx="34" ry="40" fill="{_SKIN}" stroke="{_INK}" stroke-width="1.5"/>'
            f'<ellipse cx="{cx-13}" cy="{cy-2}" rx="3" ry="2.2" fill="{_INK}"/>'
            f'<ellipse cx="{cx+13}" cy="{cy-2}" rx="3" ry="2.2" fill="{_INK}"/>'
            f'<path d="M{cx-18} {cy-12} q6 -4 12 0 M{cx+6} {cy-12} q6 -4 12 0" stroke="{_INK}" stroke-width="2" fill="none"/>'
            f'<path d="M{cx-5} {cy+8} q5 3 10 0" stroke="#7a3b2e" stroke-width="2" fill="none"/>')


def _svg(cat: str) -> str:
    head = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 240" preserveAspectRatio="xMidYMid slice" width="100%" height="100%">'
    if cat == "commute":  # 집현전 학사: 갓 + 푸른 도포
        return head + (
            '<defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b1230"/><stop offset="1" stop-color="#2b2350"/></linearGradient></defs>'
            '<rect width="200" height="240" fill="url(#g1)"/><circle cx="160" cy="42" r="16" fill="#f4e8c1" opacity=".9"/>'
            '<g fill="#fff" opacity=".7"><circle cx="30" cy="30" r="1.5"/><circle cx="60" cy="55" r="1"/><circle cx="120" cy="25" r="1.2"/><circle cx="175" cy="90" r="1"/></g>'
            '<path d="M18 240 C28 178 66 164 100 164 C134 164 172 178 182 240Z" fill="#2b4a7a"/>'
            '<path d="M84 164 L100 200 L116 164" fill="#e9e2d0"/>'
            f'<rect x="90" y="140" width="20" height="28" fill="{_SKIN}"/>' + _face() +
            '<path d="M84 128 q16 18 32 0" stroke="#2a1f16" stroke-width="2.5" fill="none"/>'
            '<ellipse cx="100" cy="80" rx="64" ry="14" fill="#16161a" opacity=".95"/>'
            '<rect x="72" y="38" width="56" height="42" rx="12" fill="#1d1d22"/>'
            '<path d="M70 86 L66 140 M130 86 L134 140" stroke="#a83232" stroke-width="3"/>'
            '<rect x="138" y="196" width="46" height="9" rx="2" fill="#d9c89a" transform="rotate(-18 160 200)"/></svg>')
    if cat == "love":  # 후궁: 쪽머리 + 비녀 + 분홍 당의
        return head + (
            '<defs><linearGradient id="g2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2a0d1c"/><stop offset="1" stop-color="#5a1f35"/></linearGradient></defs>'
            '<rect width="200" height="240" fill="url(#g2)"/>'
            '<g fill="#ffb347" opacity=".55"><circle cx="30" cy="40" r="9"/><circle cx="172" cy="62" r="7"/><circle cx="160" cy="28" r="4"/></g>'
            '<path d="M18 240 C30 180 66 166 100 166 C134 166 170 180 182 240Z" fill="#c4506a"/>'
            '<path d="M82 166 L100 204 L118 166" fill="#f6e9e4"/>'
            '<ellipse cx="100" cy="100" rx="46" ry="52" fill="#14100f"/><circle cx="100" cy="54" r="22" fill="#14100f"/>'
            f'<rect x="90" y="140" width="20" height="28" fill="{_SKIN}"/>' + _face() +
            '<path d="M92 124 q8 6 16 0" stroke="#b5303f" stroke-width="3.5" fill="none"/>'
            '<line x1="78" y1="58" x2="122" y2="50" stroke="#e8c15a" stroke-width="3.5" stroke-linecap="round"/><circle cx="124" cy="50" r="5" fill="#e8c15a"/>'
            '<g fill="#ff8fa8"><circle cx="70" cy="88" r="6"/><circle cx="76" cy="82" r="5"/><circle cx="66" cy="95" r="4"/></g></svg>')
    if cat == "career":  # 이조판서: 사모 + 붉은 관복 + 수염
        return head + (
            '<defs><linearGradient id="g3" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#07252b"/><stop offset="1" stop-color="#14274a"/></linearGradient></defs>'
            '<rect width="200" height="240" fill="url(#g3)"/>'
            '<path d="M14 240 C26 180 66 164 100 164 C134 164 174 180 186 240Z" fill="#9b2c2c"/>'
            '<rect x="82" y="190" width="36" height="36" rx="4" fill="#d9b04c"/><path d="M90 200 h20 M90 208 h20 M90 216 h20" stroke="#7a1f1f" stroke-width="2"/>'
            f'<rect x="90" y="140" width="20" height="28" fill="{_SKIN}"/>' + _face() +
            '<path d="M80 128 Q100 190 120 128 Q100 146 80 128Z" fill="#c9c9c9" stroke="#8a8a8a"/>'
            '<path d="M60 78 Q100 14 140 78 Z" fill="#141416"/><rect x="26" y="52" width="46" height="9" rx="3" fill="#141416"/><rect x="128" y="52" width="46" height="9" rx="3" fill="#141416"/>'
            '<rect x="64" y="76" width="72" height="8" fill="#141416"/></svg>')
    # wealth: 개성 상인(대행수): 망건·탕건 + 갈색 두루마기 + 엽전
    return head + (
        '<defs><linearGradient id="g4" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2b1a08"/><stop offset="1" stop-color="#5a3c12"/></linearGradient></defs>'
        '<rect width="200" height="240" fill="url(#g4)"/>'
        '<path d="M16 240 C28 180 66 164 100 164 C134 164 172 180 184 240Z" fill="#7a5320"/>'
        '<path d="M82 164 L100 204 L118 164" fill="#e9dcb4"/>'
        f'<rect x="90" y="140" width="20" height="28" fill="{_SKIN}"/>' + _face() +
        '<path d="M80 126 q20 10 40 0" stroke="#2a1f16" stroke-width="4" fill="none"/>'
        '<rect x="66" y="76" width="68" height="12" rx="4" fill="#3a2a12"/><rect x="78" y="48" width="44" height="34" rx="10" fill="#2a1c0a"/>'
        '<circle cx="160" cy="196" r="24" fill="#e0b84a" stroke="#8a6a1a" stroke-width="3"/><rect x="152" y="188" width="16" height="16" fill="#5a3c12"/></svg>')


@lru_cache(maxsize=16)
def _image_uri(path: str, mtime: float) -> str:
    raw = Path(path).read_bytes()
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(raw))
        im.thumbnail((720, 900))
        if im.mode != "RGB":
            im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=86)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        ext = Path(path).suffix.lstrip(".").lower().replace("jpg", "jpeg")
        return f"data:image/{ext};base64," + base64.b64encode(raw).decode()


def custom_image(cat: str):
    for ext in EXTS:
        p = IMG_DIR / f"{cat}.{ext}"
        if p.exists():
            return str(p), p.stat().st_mtime
    return None


def portrait_html(cat: str, ratio: str = "4 / 3", extra_style: str = "") -> str:
    """카드용 큰 초상화(HTML). 줄바꿈·들여쓰기 없이 한 줄로 반환."""
    img = custom_image(cat)
    inner = (f'<img src="{_image_uri(*img)}" style="width:100%;height:100%;object-fit:cover;object-position:top"/>'
             if img else _svg(cat))
    return f'<div class="portrait" style="aspect-ratio:{ratio};{extra_style}">{inner}</div>'


def avatar_html(cat: str, size: int = 52) -> str:
    img = custom_image(cat)
    inner = (f'<img src="{_image_uri(*img)}" style="width:100%;height:100%;object-fit:cover;object-position:top"/>'
             if img else _svg(cat))
    return f'<div class="ava" style="width:{size}px;height:{size}px">{inner}</div>'
