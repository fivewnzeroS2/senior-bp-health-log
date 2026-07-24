"""혈압 서비스에서 사용하는 공통 계산 및 변환 함수."""

from typing import Literal


BloodPressureCategory = Literal[
    "normal",
    "caution",
    "high",
]


MEASUREMENT_PERIOD_LABELS = {
    "morning": "아침",
    "afternoon": "점심",
    "evening": "저녁",
    "before_sleep": "취침 전",
    "other": "기타",
}


BLOOD_PRESSURE_CATEGORY_LABELS = {
    "normal": "정상",
    "caution": "주의",
    "high": "높음",
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


def get_blood_pressure_category(
    systolic: int,
    diastolic: int,
) -> BloodPressureCategory:
    """
    수축기와 이완기 혈압을 프로젝트 표시 상태로 분류합니다.

    이 결과는 의료 진단이 아니라
    기록 화면에서 사용하는 참고 상태입니다.
    """

    # 둘 중 하나라도 높은 기준에 해당하면 높음입니다.
    if systolic >= 140 or diastolic >= 90:
        return "high"

    # 낮은 혈압값을 정상으로 표시하지 않고 주의로 분류합니다.
    if systolic < 90 or diastolic < 60:
        return "caution"

    # 정상보다 높지만 140/90 미만인 중간 범위입니다.
    if systolic >= 120 or diastolic >= 80:
        return "caution"

    return "normal"


def get_blood_pressure_category_label(
    category: BloodPressureCategory,
) -> str:
    """혈압 상태 영문 코드를 한글로 변환합니다."""

    return BLOOD_PRESSURE_CATEGORY_LABELS[category]
