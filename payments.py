"""결제 모듈.

PAYMENT_MODE=mock (기본): 테스트 결제 - 실제 청구 없이 즉시 승인 처리.
PAYMENT_MODE=live: 실제 PG(토스페이먼츠, 포트원 등) 연동 지점. 아래 TODO 참고.

실제 결제를 받으려면 사업자등록, 통신판매업 신고, PG사 계약이 먼저 필요합니다.
"""
import os
import uuid

MODE = os.environ.get("PAYMENT_MODE", "mock")


def charge(user: dict, amount: int, order_name: str):
    """returns (성공여부, 거래ID, PG사)"""
    if MODE == "mock":
        return True, "MOCK-" + uuid.uuid4().hex[:12], "mock"
    # TODO(live): PG 결제창 호출 → 리다이렉트 후 서버에서 결제 승인(confirm) API 검증 → 거래ID 반환
    #   - 토스페이먼츠: 결제창 성공 후 paymentKey/orderId/amount를 서버에서 /v1/payments/confirm 으로 승인
    #   - 승인 금액이 서버가 가진 주문 금액과 같은지 반드시 검증
    raise NotImplementedError("PAYMENT_MODE=live 는 PG 연동 구현이 필요합니다.")


def refund(provider: str, tx_id: str) -> bool:
    if provider == "mock":
        return True
    # TODO(live): PG 결제 취소 API 호출
    raise NotImplementedError("PG 환불 API 연동이 필요합니다.")
