# -*- coding: utf-8 -*-
"""
"CS 템플릿" 구글시트(읽기 전용 공유)의 각 행을 우리 소분류 체계에 매핑한다.

시트에는 소분류 컬럼이 없어서(쓰기 권한을 요청하지 않았음 - 원본 문서라 건드리지 않는 게
안전함), 이 파일에서 행 번호(시트 기준 2행부터 시작하는 데이터 행) -> 소분류로 매핑해둔다.

주의: 시트에서 행을 위쪽에 삽입/삭제하면 이 매핑이 깨진다. 새 템플릿을 추가하실 땐 시트
맨 아래에 추가하시고, 이 파일에도 해당 행 번호 -> 소분류를 추가해주세요 (또는 Claude에게
새로 추가된 템플릿들을 다시 분류해달라고 요청).

"공통"은 특정 소분류에 매이지 않는 범용 대응 스크립트(1차 대응, 정책 안내, 감정적 고객
대응 등) - 대시보드에서는 항상 참고용으로 따로 보여줌.
"""

ROW_TO_MINOR = {
    2: "공통", 3: "공통", 4: "공통",
    5: "기타", 6: "기타", 7: "기타",
    8: "배송문의",
    9: "기타",
    10: "공통", 11: "공통",
    12: "AS 여부",
    13: "공통",
    14: "잘 열림",
    15: "안열림",
    16: "케이블 구매안내",
    17: "비상 해제 요청",
    18: "충전 방법",
    19: "비상 해제 요청",
    20: "오픈 방법",
    21: "제품 사이즈, 기종 문의",
    22: "잘 열림",
    23: "제품 파손/마감 문제",
    24: "충전 안 됨",
    25: "제품 사이즈, 기종 문의",
    26: "비상 해제 가능 여부",
    27: "비상 해제 요청",
    28: "무음 모드",
    29: "회로 문제",
    30: "오픈 방법",
    31: "제품 사이즈, 기종 문의",
    32: "잘 열림", 33: "잘 열림", 34: "잘 열림", 35: "잘 열림", 36: "잘 열림",
    37: "제품 사이즈, 기종 문의",
    38: "비상 해제 요청",
    39: "기타",
    40: "제품 파손/마감 문제",
    41: "충전 방법",
    42: "충전 안 됨",
}


def load_templates(gc, sheet_id):
    """반환: [{"소분류":..., "제품":..., "질문":..., "답변":...}, ...]"""
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet("시트1")
    values = ws.get_all_values()
    if not values:
        return []
    headers = values[0]
    idx_major = headers.index("대분류") if "대분류" in headers else None
    idx_q = headers.index("질문") if "질문" in headers else None
    idx_a = headers.index("답변") if "답변" in headers else None

    templates = []
    for row_num, row in enumerate(values[1:], start=2):
        if not any(row):
            continue
        minor = ROW_TO_MINOR.get(row_num)
        if not minor:
            continue
        templates.append({
            "소분류": minor,
            "제품": row[idx_major] if idx_major is not None and len(row) > idx_major else "",
            "질문": row[idx_q] if idx_q is not None and len(row) > idx_q else "",
            "답변": row[idx_a] if idx_a is not None and len(row) > idx_a else "",
        })
    return templates
