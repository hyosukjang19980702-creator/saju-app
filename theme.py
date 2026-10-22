"""조선시대 컨셉 테마(CSS)와 히어로 영역 HTML."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@400;600;700&display=swap');
:root{--gold:#a8742a;--gold2:#7a4f12;--paper:#fffaf0;--text:#2b2118;--muted:#6f6149;--line:rgba(139,100,40,.28)}
html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea, label{font-family:'Noto Serif KR','Nanum Myeongjo',serif !important}
:root{color-scheme:light}
.stApp{background:repeating-linear-gradient(0deg,rgba(150,115,60,.035) 0 1px,transparent 1px 7px),linear-gradient(180deg,#fdf8ec 0%,#f6ebd2 100%);color:var(--text)}
.stApp [data-testid="stMarkdownContainer"] p,.stApp [data-testid="stMarkdownContainer"] li,.stApp label p,.stApp [data-testid="stCaptionContainer"]{color:#2b2118}
.stApp [data-testid="stCaptionContainer"]{color:#6f6149}
[data-testid="stAppViewContainer"]::before{content:"";display:block;height:8px;background:linear-gradient(90deg,#8c2f23 0 20%,#2f6b5a 20% 40%,#c9a24a 40% 60%,#2f5d8c 60% 80%,#8c2f23 80%)}
.price{background:#fbe9e4 !important;border-color:#a63a2a !important;color:#8c2f23 !important}
[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"]{background:#f1e5c8;border-right:1px solid var(--line)}
h1,h2,h3,h4{color:var(--gold2) !important}
a{color:var(--gold) !important}
hr{border-color:var(--line) !important}
.stButton>button,[data-testid="stLinkButton"] a,[data-testid="stFormSubmitButton"]>button{border-radius:999px;border:1px solid var(--gold);background:#fffaf0;color:var(--gold2) !important;font-weight:600}
.stButton>button[kind="primary"],[data-testid="stFormSubmitButton"]>button[kind="primaryFormSubmit"],[data-testid="stLinkButton"] a[kind="primary"]{background:linear-gradient(180deg,#d9a94f,#b9852c);color:#fff !important;border:0}
.stButton>button:hover{border-color:var(--gold2)}
.stButton>button[kind="primary"]:hover{filter:brightness(1.06);color:#fff !important}
div[data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--line) !important;background:rgba(255,252,244,.85);border-radius:16px}
[data-baseweb="input"],[data-baseweb="select"]>div,textarea{background:#fff !important;border-color:var(--line) !important;color:#2b2118 !important}
input,textarea{color:#2b2118 !important;-webkit-text-fill-color:#2b2118 !important}
[data-testid="stExpander"]{border-color:var(--line) !important;background:rgba(255,252,244,.9);border-radius:12px}
.hero{position:relative;overflow:hidden;border-radius:20px;border:1px solid var(--line);padding:20px 24px 34px;min-height:380px;
 background:radial-gradient(500px 260px at 85% 8%,#ffe9b8 0%,transparent 65%),linear-gradient(180deg,#fff4d9 0%,#f6dfb0 60%,#e9c98a 100%)}
.hero .moon{position:absolute;top:26px;right:30px;width:46px;height:46px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#fffdf2,#f3d98f 75%);box-shadow:0 0 30px 8px rgba(255,214,120,.5)}
.hero .roof{position:absolute;right:-20px;bottom:0;width:62%;opacity:.85}
.brand{display:flex;align-items:center;gap:12px;position:relative;z-index:2}
.brand .t{font-size:28px;font-weight:700;color:#5a3a0c}
.brand .s{font-size:13px;color:#8a5f1d}
.hero .copy{position:relative;z-index:2;margin-top:34px;max-width:560px}
.hero .kick{font-size:15px;color:#5f4a2a;margin-bottom:6px}
.hero .big{font-size:42px;line-height:1.2;font-weight:700;color:#3a2812}
.hero .big em{font-style:normal;color:#a8581a}
.hero .sub{margin-top:14px;font-size:14px;line-height:1.8;color:#5f4a2a}
.portrait{width:100%;border-radius:12px;overflow:hidden;border:1px solid var(--line);background:#efe2c4}
.portrait svg,.portrait img{display:block;width:100%;height:100%}
.pname{font-size:19px;font-weight:700;color:var(--gold2);margin:10px 0 0}
.ptitle{font-size:12px;color:var(--gold);letter-spacing:.04em}
.ptag{font-size:13px;color:#5b4d36;margin:6px 0 8px;line-height:1.6}
.price{display:inline-block;padding:3px 10px;border:1px solid var(--gold);border-radius:999px;font-size:12px;color:var(--gold2);background:#fff7e3}
.chat-row{display:flex;gap:10px;margin:12px 0;align-items:flex-start}
.ava{flex:0 0 auto;border-radius:50%;overflow:hidden;border:1px solid var(--gold);background:#efe2c4}
.ava svg,.ava img{display:block;width:100%;height:100%}
.chat-col{flex:1;min-width:0}
.chat-name{font-size:12px;color:var(--gold);margin-bottom:3px}
.chat-bubble{display:inline-block;max-width:100%;background:#fff;border:1px solid var(--line);color:#33250f;border-radius:4px 16px 16px 16px;padding:12px 15px;line-height:1.75;font-size:15px;box-shadow:0 2px 8px rgba(120,90,30,.12)}
.chat-bubble b{color:#8a2a1a}
.lock{border:1px dashed var(--line);border-radius:12px;padding:12px 14px;color:var(--muted);font-size:14px}
@media (max-width:640px){.hero .big{font-size:32px}.hero .roof{width:90%}}
</style>
"""

ROOF = ('<svg class="roof" viewBox="0 0 400 140" xmlns="http://www.w3.org/2000/svg"><g fill="#6b4a22">'
        '<path d="M20 120 Q120 100 200 70 Q280 100 380 120 L380 140 L20 140Z"/><path d="M60 100 Q200 60 340 100 L330 112 Q200 78 70 112Z"/>'
        '<rect x="90" y="112" width="220" height="28"/></g><g fill="#f6dfb0" opacity=".8"><rect x="120" y="118" width="14" height="18"/><rect x="190" y="118" width="14" height="18"/><rect x="260" y="118" width="14" height="18"/></g></svg>')

EMBLEM = ('<svg width="52" height="52" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" fill="none" stroke="#a8742a" stroke-width="1.6">'
          '<circle cx="32" cy="32" r="29"/><path d="M32 8 L40 28 L58 28 L44 40 L50 58 L32 46 L14 58 L20 40 L6 28 L24 28Z"/><circle cx="32" cy="32" r="5" fill="#a8742a"/></svg>')


def hero_html(service: str) -> str:
    return (f'<div class="hero"><div class="moon"></div>{ROOF}'
            f'<div class="brand">{EMBLEM}<div><div class="t">{service}</div><div class="s">조선 명리학으로 풀어내는 당신의 운명</div></div></div>'
            '<div class="copy"><div class="kick">조선시대 천문학과 고서에서 찾은</div>'
            '<div class="big">AI가 풀어낸<br><em>당신의 사주</em></div>'
            '<div class="sub">천문과 고전의 지혜에,<br>AI의 정밀한 해석을 더한<br>프리미엄 운세 서비스</div>'
            '</div></div>')


FEATURES = ""
