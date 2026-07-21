"""혈압 서비스에서 사용하는 공통 계산 및 변환 함수."""


MEASUREMENT_PERIOD_LABELS = {
    "morning": "아침",
    "afternoon": "점심",
    "evening": "저녁",
    "before_sleep": "취침 전",
    "other": "기타",
}


def get_measurement_period_label(
    measurement_period: str | None,
) -> str | None:
    """영문 측정 시간대 코드를 한글로 변환합니다."""

    if measurement_period is None:
        return None

    return MEASUREMENT_PERIOD_LABELS.get(
        measurement_period,
        "기타",
    )