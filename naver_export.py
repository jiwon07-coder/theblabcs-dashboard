# -*- coding: utf-8 -*-
"""
네이버 톡톡 대화창에서 그냥 긁어서(복사) 붙여넣은 텍스트를 읽기 좋은 형태로 정리한다.
네이버 톡톡은 카카오 비즈니스와 달리 "엑셀로 내보내기" 기능이 없어서, 사용자가 대화창을
마우스로 드래그해 복사한 원본 텍스트를 그대로 받아 파싱한다.

**2026-09-22 형식이 통째로 바뀐 걸 발견함** - 예전엔 메시지마다 "* "(별표+공백) 접두어가
붙어있다고 가정했는데(그 가정으로 몇 달 잘 동작했음), 실제 실패 사례를 받아보니 그 접두어가
전혀 없는 새 형식이었음:

  메리곰                          <- 고객 메시지: 이름이 접두어 없이 그냥 한 줄, 그 다음이 본문
  예전에 구매하고 쓰고 있었는데...
                                  <- 빈 줄
  오후 4:10                       <- 시각(이 메시지, 즉 방금 고객 메시지의 시각으로 보임)
  9. 14. (월)                     <- 날짜 구분선(대화 중 날짜가 넘어갔다는 표시로 추정,
                                     특정 메시지 소유가 아니라 그냥 버려도 되는 구분자)
  안녕하세요 고객님!                <- 상담원 메시지: 이름 줄 자체가 없음, 바로 본문 시작
  ...
  감사합니다.
                                  <- 빈 줄
  툴팁 열기                        <- 네이버 톡톡 UI가 붙이는 채널 프로필 카드의 시작 표시
  더비랩                          <- (실제 대화 내용이 아니라 채널 소개 카드 - 통째로 버림)
  더비랩과 함께 완전한 몰입을 느껴 보세요.
  http://pf.kakao.com/_IrxibG

이 형식이 앞으로 또 바뀔 수 있으니(공식 API가 아니라 UI 복사 결과에 의존하는 구조라서),
새로 실패하는 사례가 생기면 실제 원본 텍스트를 받아서 이 파일을 다시 맞출 것.

화자 구분: "읽음" 표시는 상대가 읽었을 때만 붙어서 복사 시점에 따라 있다 없다 하므로
쓰지 않음(예전과 동일한 이유). 대신:
  1) customer_name이 주어지면, 시각으로 나뉜 덩어리 중 첫 줄이 customer_name과 정확히
     일치하는 덩어리만 고객으로 판단(가장 정확함 - 폼에서 닉네임을 받아서 넘겨줄 것을 권장).
  2) 안 주어졌으면, 여러 번 반복해서 등장하는 첫 줄을 고객 이름으로 추정한다(고객 이름은
     보통 여러 번 반복되지만 상담원 메시지의 첫 줄은 매번 다른 문장이라 반복되지 않는다는
     점을 이용한 추정 - 완벽하지 않음, 예전과 동일한 방식).
"""
import re
from collections import Counter

_TIME_RE = re.compile(r"^(읽음)?(오전|오후)\s*\d{1,2}:\d{2}$")
_DATE_DIVIDER_RE = re.compile(r"^\d{1,2}\.\s*\d{1,2}\.\s*\([월화수목금토일]\)$")
_NOISE_START_RE = re.compile(r"^툴팁\s*열기$")


def _strip_noise_tail(lines):
    """"툴팁 열기" 줄부터는 실제 대화가 아니라 네이버 톡톡이 붙이는 채널 프로필 카드
    (채널명/소개문구/링크)라서 통째로 버림. 안 나오면 그대로 둠."""
    for i, line in enumerate(lines):
        if _NOISE_START_RE.match(line.strip()):
            return lines[:i]
    return lines


def _split_blocks(raw_text):
    """시각 줄("오후 4:10" 같은)을 경계로 덩어리를 나눈다. 시각 줄 자체와 날짜 구분선
    ("9. 14. (월)")은 내용이 아니라서 버린다."""
    lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    chunks, current = [], []
    for line in lines:
        stripped = line.strip()
        if _TIME_RE.match(stripped):
            chunks.append(current)
            current = []
            continue
        if _DATE_DIVIDER_RE.match(stripped):
            continue
        current.append(line)
    chunks.append(current)

    result = []
    for chunk in chunks:
        chunk = _strip_noise_tail(chunk)
        while chunk and not chunk[0].strip():
            chunk.pop(0)
        while chunk and not chunk[-1].strip():
            chunk.pop()
        if chunk:
            result.append(chunk)
    return result


def _guess_customer_name(blocks):
    counts = Counter(chunk[0].strip() for chunk in blocks if chunk and chunk[0].strip())
    candidates = [name for name, c in counts.items() if c >= 2 and len(name) <= 12]
    return candidates[0] if candidates else None


def parse_naver_text(raw_text, customer_name=None):
    """반환: "고객: ..." / "상담원: ..." 줄로 정리된 대화 전문(문자열)."""
    if not raw_text:
        return ""
    blocks = _split_blocks(raw_text)
    if not blocks:
        return ""

    name = (customer_name or "").strip() or _guess_customer_name(blocks)

    messages = []
    for chunk in blocks:
        is_customer = name is not None and chunk[0].strip() == name
        body_lines = chunk[1:] if is_customer else chunk
        body = "\n".join(body_lines).strip()
        if body:
            role = "고객" if is_customer else "상담원"
            messages.append(f"{role}: {body}")
    return "\n\n".join(messages)
