"""이메일 발송(SMTP). 환경변수/Secrets로 설정:

SMTP_HOST, SMTP_PORT(기본 587), SMTP_USER, SMTP_PASSWORD, SMTP_FROM(선택, 기본 SMTP_USER)
예) Gmail: smtp.gmail.com / 587 / 내Gmail주소 / 앱 비밀번호(16자리)
"""
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr


def configured() -> bool:
    return all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"))


def explain(e: Exception) -> str:
    """관리자 진단용: 발송 실패 원인을 쉬운 말로 설명."""
    name = type(e).__name__
    if isinstance(e, smtplib.SMTPAuthenticationError):
        return "로그인 실패: SMTP_USER(보내는 Gmail 주소)와 앱 비밀번호 16자리를 확인하세요. 평소 쓰는 Gmail 비밀번호는 사용할 수 없습니다."
    if isinstance(e, (smtplib.SMTPConnectError, ConnectionError, TimeoutError, OSError)):
        return "메일 서버에 연결하지 못했습니다. SMTP_HOST(smtp.gmail.com)와 SMTP_PORT(587)를 확인하세요."
    if isinstance(e, smtplib.SMTPSenderRefused):
        return "보내는 주소가 거부되었습니다. SMTP_FROM을 비우거나 SMTP_USER와 같은 주소로 설정하세요."
    if isinstance(e, smtplib.SMTPRecipientsRefused):
        return "받는 주소가 거부되었습니다. 이메일 주소를 확인하세요."
    return f"{name}: {e}"


def send(to: str, subject: str, body: str, sender_name: str = "") -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"].replace(" ", "")  # Gmail 앱 비밀번호의 공백 제거
    from_addr = os.environ.get("SMTP_FROM") or user

    msg = EmailMessage()
    msg["From"] = formataddr((sender_name, from_addr)) if sender_name else from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=20) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.starttls(context=ctx)
            s.login(user, password)
            s.send_message(msg)


def send_code(to: str, code: str, purpose_label: str, service_name: str) -> None:
    send(
        to,
        f"[{service_name}] {purpose_label} 인증코드: {code}",
        f"{service_name} {purpose_label} 인증코드입니다.\n\n"
        f"    {code}\n\n"
        "10분 안에 입력해 주세요. 본인이 요청하지 않았다면 이 메일을 무시하셔도 됩니다.",
        sender_name=service_name,
    )
