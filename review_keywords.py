# -*- coding: utf-8 -*-
"""
리뷰에서 광고소재로 쓸만한 서사 유형을 키워드/정규식으로 찾아낸다. 4점 이상 리뷰만 대상.
export_dashboard.py의 classify_inquiry와 같은 방식 - 새 표현을 발견하면 아래 PATTERNS
리스트에 추가하면 됨.

- HESITATION_PATTERNS: "반신반의하다가 결국 만족했다"류의 망설임→만족 서사
- COMPARISON_PATTERNS: "여러 제품 비교하다가 여기로 정했다"류의 비교구매 서사
"""
import re

# 리뷰 탭은 현재 판매 중인 이 두 제품만 참고하면 된다고 확정함(2026-09-09) - 오리지널/미니/
# 오리지널 케이블/미분류 리뷰는 시트엔 그대로 있지만 대시보드·단어빈도 분석엔 안 씀.
# app.py의 fetch_reviews()와 review_noun_frequency.py의 get_reviews() 둘 다 이걸로 필터링함.
REVIEW_PRODUCTS = ["오리지널 V2", "프로"]

# 카페24가 리뷰 끝에 자동으로 붙이는 "YYYY-MM-DD ... 에(서) 등록된/작성된 {채널} 구매평" 꼬리.
# 괄호 유무/"등록된"·"작성된"/"에"·"에서" 조합으로 실제 4가지 변형이 확인됨(2026-09-07,
# review_noun_frequency.py 작업 중 발견) - 안 지우면 "스마트스토어"가 "스마트"/"스토어"로
# 쪼개지거나, 의심 포인트 인용구 끝에 이 날짜/채널 텍스트가 지저분하게 붙어버림.
_PLATFORM_TAIL_RE = re.compile(r"\(?\d{4}-\d{2}-\d{2}[^\n]{0,30}?에서?\s?(등록|작성)된[^\n]*")


def strip_platform_tail(text):
    return _PLATFORM_TAIL_RE.sub("", text or "")


HESITATION_PATTERNS = [
    r"반신반의",
    r"걱정.{0,12}(했는데|했지만|했던|되서|됐는데|많았)",
    r"고민.{0,12}(하다가|했는데|끝에|하던|하고|많이)",
    r"망설이|망설였",
    r"살까\s?말까",
    r"살지\s?말지",
    r"큰\s?기대.{0,10}(안|없이|못)",
    r"기대.{0,10}안\s?했는데",
    r"의심.{0,10}(했는데|스러웠|이\s?들었)",
    r"효과.{0,10}있을까",
    r"소용\s?없을\s?줄",
    r"별로일\s?줄",
    r"뭔가\s?싶었는데",
]

COMPARISON_PATTERNS = [
    r"비교하다가",
    r"비교.{0,10}(해보고|해보다가|끝에)",
    r"알아보다가",
    r"찾아보다가",
    r"검색하다가",
    r"이것저것.{0,15}(알아보|비교|찾아보|검색)",  # "이것저것" 단독은 "폰 없이 이것저것 하다보니" 같은 오탐이 있어서 비교 동사와 같이 나올 때만
    r"여러\s?(제품|곳|사이트|브랜드|회사)",
    r"다른\s?(제품|브랜드).{0,15}(써봤|사용해봤|써보다가|사봤)",
]


def _matches_any(text, patterns):
    if not text:
        return False
    return any(re.search(p, text) for p in patterns)


def has_hesitation(text):
    return _matches_any(text, HESITATION_PATTERNS)


def has_comparison(text):
    return _matches_any(text, COMPARISON_PATTERNS)


def _filter_by_rating(reviews, min_rating, match_fn):
    """reviews: [{'별점':..., '리뷰내용':..., ...}, ...] (구글시트 "리뷰" 탭 dict 형태)"""
    result = []
    for r in reviews:
        try:
            rating = float(r.get("별점") or 0)
        except ValueError:
            rating = 0
        if rating < min_rating:
            continue
        if match_fn(r.get("리뷰내용", "")):
            result.append(r)
    return result


def find_hesitation_reviews(reviews, min_rating=4):
    return _filter_by_rating(reviews, min_rating, has_hesitation)


def find_comparison_reviews(reviews, min_rating=4):
    return _filter_by_rating(reviews, min_rating, has_comparison)


PARENT_PATTERNS = [
    # "아이"/"딸"은 단어 자체가 흔해서 무관한 단어의 일부로 걸리는 오탐이 있어 제외 처리함
    # (실제 리뷰로 검증: "아이폰"/"아이디어"/"아이템", "딸기"/"딸깍" - 2026-09-09).
    r"아이(?!폰|디어|템)",
    r"딸(?!기|깍)",
    r"아들", r"자녀", r"애들", r"우리\s?애", r"저희\s?아이", r"학부모",
    r"중학생.{0,10}(아들|딸)", r"고등학생.{0,10}(아들|딸)", r"제\s?아이",
]

STUDENT_PATTERNS = [
    # "공부"/"시험"류 표현은 부모가 자녀 얘기하면서도 흔히 씀(예: "아이가 공부할 때",
    # "아이 시험기간이라") - classify_reviewer가 **부모 신호를 먼저 확인하고 우선시**하도록
    # 바뀌어서(2026-09-10), 이제 이 표현들이 부모 리뷰와 겹쳐도 안전하게 넓게 잡을 수 있음
    # (부모 패턴에 안 걸린 나머지 리뷰 중에서만 아래 표현으로 학생 본인을 판단하게 됨).
    r"공부", r"시험", r"제\s?방에서",
    r"자취", r"기숙사", r"인강\s?볼\s?때",
]


def classify_reviewer(text):
    """리뷰 작성자가 "부모"(자녀 얘기를 하며 씀)인지 "학생 본인"(1인칭으로 본인 얘기)인지
    키워드로 추정. **부모 신호를 먼저 확인**하고(자녀 얘기를 하면서 "공부"/"시험" 같은
    표현도 같이 쓰는 경우가 많아서, 부모 쪽이 더 확실한 신호로 보고 우선시함), 부모
    패턴에 안 걸린 리뷰에 한해서만 학생 본인 패턴을 확인함. 둘 다 안 걸리면 "판단불가".
    새 표현을 발견하면 PARENT_PATTERNS/STUDENT_PATTERNS에 추가하면 됨(export_dashboard.py의
    classify_inquiry와 같은 방식)."""
    if not text:
        return "판단불가"
    if _matches_any(text, PARENT_PATTERNS):
        return "부모"
    if _matches_any(text, STUDENT_PATTERNS):
        return "학생 본인"
    return "판단불가"


def extract_hesitation_snippet(text, context=40):
    """망설임 표현이 매칭된 부분 앞뒤로 짧게 잘라서 반환 - "구매 전 의심 포인트" 목록처럼
    리뷰 전문이 아니라 한눈에 훑어볼 짧은 인용구가 필요할 때 씀. 매칭 없으면 빈 문자열."""
    text = strip_platform_tail(text)
    if not text:
        return ""
    for p in HESITATION_PATTERNS:
        m = re.search(p, text)
        if m:
            start = max(0, m.start() - context)
            end = min(len(text), m.end() + context)
            snippet = re.sub(r"\s+", " ", text[start:end]).strip()
            return ("…" if start > 0 else "") + snippet + ("…" if end < len(text) else "")
    return ""
