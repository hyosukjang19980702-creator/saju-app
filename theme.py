"""조선시대 컨셉 테마(CSS)와 히어로 영역 HTML."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@400;600;700&display=swap');
:root{--gold:#d4b779;--gold2:#f1dba4;--ink:#0b0907;--panel:#15110d;--paper:#efe2c4;--text:#efe6d2;--muted:#b8a98a}
html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea, label{font-family:'Noto Serif KR','Nanum Myeongjo',serif !important}
.stApp{background:radial-gradient(1200px 600px at 80% -10%,#1d1a3a 0%,transparent 60%),linear-gradient(180deg,#0a0c1a 0%,#0e0b0a 40%,#0b0907 100%);color:var(--text)}
[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"]{background:#0d0a08;border-right:1px solid rgba(212,183,121,.2)}
h1,h2,h3,h4{color:var(--gold2) !important;letter-spacing:.01em}
a{color:var(--gold) !important}
hr{border-color:rgba(212,183,121,.2) !important}
.stButton>button,[data-testid="stLinkButton"] a,[data-testid="stFormSubmitButton"]>button{border-radius:999px;border:1px solid var(--gold);background:transparent;color:var(--gold2) !important;font-weight:600}
.stButton>button[kind="primary"],[data-testid="stFormSubmitButton"]>button[kind="primaryFormSubmit"],[data-testid="stLinkButton"] a[kind="primary"]{background:linear-gradient(180deg,#f3e3b6,#cfae6c);color:#2a1d08 !important;border:0}
.stButton>button:hover{border-color:var(--gold2);color:#fff !important}
.stButton>button[kind="primary"]:hover{filter:brightness(1.07);color:#2a1d08 !important}
div[data-testid="stVerticalBlockBorderWrapper"]{border-color:rgba(212,183,121,.28) !important;background:rgba(20,16,12,.72);border-radius:16px}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.parch){background:linear-gradient(135deg,#f1e5c8,#e2cf9f);border-color:#b99a5a !important}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.parch) *{color:#3a2b14 !important}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.parch) .stButton>button{border-color:#7a5a1e;color:#4a3410 !important}
[data-baseweb="input"],[data-baseweb="select"]>div,textarea{background:#17120d !important;border-color:rgba(212,183,121,.3) !important}
[data-testid="stExpander"]{border-color:rgba(212,183,121,.3) !important;background:rgba(20,16,12,.6);border-radius:12px}
.hero{position:relative;overflow:hidden;border-radius:20px;border:1px solid rgba(212,183,121,.3);padding:20px 24px 34px;min-height:430px;
 background:radial-gradient(2px 2px at 12% 18%,#fff,transparent),radial-gradient(1.5px 1.5px at 28% 42%,#fff,transparent),radial-gradient(1.5px 1.5px at 55% 12%,#fff,transparent),
 radial-gradient(2px 2px at 72% 30%,#ffe9a8,transparent),radial-gradient(1px 1px at 88% 52%,#fff,transparent),radial-gradient(1.5px 1.5px at 40% 70%,#fff,transparent),
 radial-gradient(900px 380px at 100% 0%,#2a2350 0%,transparent 60%),linear-gradient(180deg,#070a1c 0%,#15132b 45%,#33200f 100%)}
.hero .moon{position:absolute;top:26px;right:30px;width:46px;height:46px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#fffbe8,#d8cfae 70%);box-shadow:0 0 30px 6px rgba(255,244,200,.35)}
.hero .roof{position:absolute;right:-20px;bottom:0;width:62%;opacity:.9}
.brand{display:flex;align-items:center;gap:12px;position:relative;z-index:2}
.brand .t{font-size:28px;font-weight:700;color:var(--gold2)}
.brand .s{font-size:13px;color:var(--gold)}
.hero .copy{position:relative;z-index:2;margin-top:38px;max-width:560px}
.hero .kick{font-size:15px;color:#e8dcc0;margin-bottom:6px}
.hero .big{font-size:42px;line-height:1.2;font-weight:700;color:#fff}
.hero .big em{font-style:normal;color:var(--gold2)}
.hero .sub{margin-top:14px;font-size:14px;line-height:1.8;color:#d9ccb0}
.hero .cta{display:inline-block;margin-top:22px;padding:13px 28px;border-radius:999px;background:linear-gradient(180deg,#f3e3b6,#cfae6c);color:#2a1d08 !important;font-weight:700;text-decoration:none}
.feat{display:flex;flex-wrap:wrap;gap:6px;margin:18px 0 6px}
.feat div{flex:1 1 130px;text-align:center;padding:10px 6px;border-right:1px solid rgba(212,183,121,.2)}
.feat div:last-child{border-right:0}
.feat .ic{width:44px;height:44px;margin:0 auto 8px;border:1px solid var(--gold);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px;color:var(--gold2)}
.feat b{display:block;font-size:14px;color:#f3e8cc}.feat span{font-size:12px;color:var(--muted)}
.portrait{width:100%;border-radius:12px;overflow:hidden;border:1px solid rgba(212,183,121,.35);background:#111}
.portrait svg,.portrait img{display:block;width:100%;height:100%}
.pname{font-size:19px;font-weight:700;color:var(--gold2);margin:10px 0 0}
.ptitle{font-size:12px;color:var(--gold);letter-spacing:.04em}
.ptag{font-size:13px;color:#d8ccb2;margin:6px 0 8px;line-height:1.6}
.price{display:inline-block;padding:3px 10px;border:1px solid var(--gold);border-radius:999px;font-size:12px;color:var(--gold2)}
.chat-row{display:flex;gap:10px;margin:12px 0;align-items:flex-start}
.ava{flex:0 0 auto;border-radius:50%;overflow:hidden;border:1px solid var(--gold);background:#111}
.ava svg,.ava img{display:block;width:100%;height:100%}
.chat-col{flex:1;min-width:0}
.chat-name{font-size:12px;color:var(--gold);margin-bottom:3px}
.chat-bubble{display:inline-block;max-width:100%;background:linear-gradient(135deg,#f1e5c8,#e5d3a6);color:#33250f;border-radius:4px 16px 16px 16px;padding:12px 15px;line-height:1.75;font-size:15px;box-shadow:0 2px 10px rgba(0,0,0,.35)}
.chat-bubble b{color:#7a2a1a}
.lock{border:1px dashed rgba(212,183,121,.5);border-radius:12px;padding:12px 14px;color:var(--muted);font-size:14px}
.parch{display:none}
@media (max-width:640px){.hero .big{font-size:32px}.hero .roof{width:90%}}
</style>
"""

ROOF = ('<svg class="roof" viewBox="0 0 400 140" xmlns="http://www.w3.org/2000/svg"><g fill="#120d0a">'
        '<path d="M20 120 Q120 100 200 70 Q280 100 380 120 L380 140 L20 140Z"/><path d="M60 100 Q200 60 340 100 L330 112 Q200 78 70 112Z"/>'
        '<rect x="90" y="112" width="220" height="28"/></g><g fill="#d4b779" opacity=".55"><rect x="120" y="118" width="14" height="18"/><rect x="190" y="118" width="14" height="18"/><rect x="260" y="118" width="14" height="18"/></g></svg>')

EMBLEM = ('<svg width="52" height="52" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="#d4b779" stroke-width="1.6">'
          '<circle cx="32" cy="32" r="29"/><path d="M32 8 L40 28 L58 28 L44 40 L50 58 L32 46 L14 58 L20 40 L6 28 L24 28Z"/><circle cx="32" cy="32" r="5" fill="#d4b779"/></svg>')


def hero_html(service: str) -> str:
    return (f'<div class="hero"><div class="moon"></div>{ROOF}'
            f'<div class="brand">{EMBLEM}<div><div class="t">{service}</div><div class="s">조선의 하늘을 잇는, 당신의 운명</div></div></div>'
            '<div class="copy"><div class="kick">조선시대 천문학과 고서에서 찾은</div>'
            '<div class="big">AI가 풀어낸<br><em>당신의 사주</em></div>'
            '<div class="sub">천문과 고전의 지혜에,<br>AI의 정밀한 해석을 더한<br>프리미엄 운세 서비스</div>'
            '<a class="cta" href="#pick">사주 풀이 시작하기 &nbsp;→</a></div></div>')


FEATURES = ('<div class="feat">'
            '<div><div class="ic">✦</div><b>정확한 사주 분석</b><span>절기 기준 명식 계산</span></div>'
            '<div><div class="ic">📖</div><b>고전의 지혜</b><span>전통 명리 해석법</span></div>'
            '<div><div class="ic">🤖</div><b>맞춤형 인사이트</b><span>성향과 운의 흐름 분석</span></div>'
            '<div><div class="ic">🧭</div><b>미래를 여는 조언</b><span>현명한 선택을 위해</span></div></div>')
