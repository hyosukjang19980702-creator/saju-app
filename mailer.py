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


def send(to: str, subject: str, body: str, sender_name: str = "") -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
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
