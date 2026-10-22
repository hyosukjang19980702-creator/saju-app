"""결제 모듈 (토스페이먼츠 연동 + 테스트용 mock).

모드(자동 판별)
- toss : TOSS_CLIENT_KEY 와 TOSS_SECRET_KEY 가 모두 설정되어 있으면 사용
          · 키가 test_ 로 시작 → 테스트 결제(실제 청구 없음)
          · 키가 live_ 로 시작 → 실결제 (토스페이먼츠 계약 완료 후 발급)
- mock : 위 키가 없으면 가짜 결제(즉시 승인, 청구 없음)

보안 원칙: 시크릿 키(TOSS_SECRET_KEY)는 서버에서만 사용하며 화면/브라우저로 내보내지 않습니다.
결제 승인 시 금액은 항상 서버 DB에 저장된 주문 금액으로 검증합니다.
"""
import base64
import os
import uuid

import requests

API_BASE = os.environ.get("TOSS_API_BASE", "https://api.tosspayments.com")


class PaymentError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code, self.message = code, message


def client_key() -> str:
    return os.environ.get("TOSS_CLIENT_KEY", "").strip()


def _secret() -> str:
    return os.environ.get("TOSS_SECRET_KEY", "").strip()


def mode() -> str:
    return "toss" if client_key() and _secret() else "mock"


def is_live() -> bool:
    return mode() == "toss" and _secret().startswith("live_")


def mode_label() -> str:
    if mode() == "mock":
        return "테스트 결제(mock) — 실제 청구 없음"
    return "토스페이먼츠 실결제(live)" if is_live() else "토스페이먼츠 테스트 키 — 실제 청구 없음"


def _headers(idem: str | None = None) -> dict:
    auth = base64.b64encode((_secret() + ":").encode()).decode()  # 콜론(:) 필수
    h = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
    if idem:
        h["Idempotency-Key"] = idem
    return h


def _json(r: requests.Response) -> dict:
    try:
        return r.json()
    except Exception:
        return {}


def _call(method: str, path: str, idem: str | None = None, body: dict | None = None) -> tuple[int, dict]:
    try:
        r = requests.request(method, API_BASE + path, headers=_headers(idem), json=body, timeout=30)
    except requests.RequestException as e:
        raise PaymentError("NETWORK", f"결제사 서버와 통신하지 못했습니다. ({type(e).__name__})")
    return r.status_code, _json(r)


def lookup_by_order(order_id: str) -> dict:
    status, data = _call("GET", f"/v1/payments/orders/{order_id}")
    if status != 200:
        raise PaymentError(data.get("code", "LOOKUP_FAILED"), data.get("message", f"HTTP {status}"))
    return data


def confirm(payment_key: str, order_id: str, amount: int) -> dict:
    """결제 승인. amount 는 반드시 서버 DB의 주문 금액을 넘길 것."""
    idem = str(uuid.uuid5(uuid.NAMESPACE_URL, "saju-confirm:" + order_id))  # 같은 주문 중복 승인 방지
    status, data = _call("POST", "/v1/payments/confirm", idem,
                         {"paymentKey": payment_key, "orderId": order_id, "amount": int(amount)})
    if status != 200:
        if data.get("code") == "ALREADY_PROCESSED_PAYMENT":
            data = lookup_by_order(order_id)  # 이미 승인됨 → 조회로 확인
        else:
            raise PaymentError(data.get("code", "UNKNOWN"), data.get("message", f"HTTP {status}"))
    if data.get("status") != "DONE":
        raise PaymentError("NOT_DONE", f"결제가 완료 상태가 아닙니다. (status={data.get('status')})")
    if data.get("orderId") != order_id or int(data.get("totalAmount", -1)) != int(amount):
        raise PaymentError("MISMATCH", "결제 정보가 주문과 일치하지 않습니다.")
    return data


def refund(provider: str, tx_id: str, reason: str = "고객 요청") -> bool:
    if provider == "mock":
        return True
    if provider == "toss":
        idem = str(uuid.uuid5(uuid.NAMESPACE_URL, "saju-cancel:" + tx_id))
        status, data = _call("POST", f"/v1/payments/{tx_id}/cancel", idem, {"cancelReason": reason})
        if status == 200:
            return True
        raise PaymentError(data.get("code", "UNKNOWN"), data.get("message", f"HTTP {status}"))
    raise PaymentError("UNSUPPORTED", f"지원하지 않는 결제사입니다: {provider}")


def charge(user: dict, amount: int, order_name: str):
    """mock 전용 즉시 결제. returns (성공여부, 거래ID, PG사)"""
    return True, "MOCK-" + uuid.uuid4().hex[:12], "mock"
