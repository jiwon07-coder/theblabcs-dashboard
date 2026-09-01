# -*- coding: utf-8 -*-
"""
네이버 톡톡 대화창에서 그냥 긁어서(복사) 붙여넣은 텍스트를 읽기 좋은 형태로 정리한다.
네이버 톡톡은 카카오 비즈니스와 달리 "엑셀로 내보내기" 기능이 없어서, 사용자가 대화창을
마우스로 드래그해 복사한 원본 텍스트를 그대로 받아 파싱한다.

원본 형태 (관찰된 패턴):
  * 김재희                      <- 고객 메시지: "* " 다음 줄이 이름, 그 다음 줄부터 본문
  택배를 못 받았어요...
  오후 1:45                     <- 시각
  * 안녕하세요, 고객님!          <- 상담원 메시지: 이름 줄이 없고 "* " 바로 뒤가 본문 시작
  배송 완료로 조회되는데...
  읽음오후 2:12                 <- 시각 앞에 "읽음"이 붙기도 함

주의: 시각 줄의 "읽음" 표시는 "상대가 이미 읽었다"는 뜻이라 상담원이 대화를 복사하는
"시점"에 따라 안 붙어있을 수도 있음(상대가 아직 안 읽었으면). 그래서 이걸로 화자를
구분하면 틀릴 수 있어 쓰지 않는다. 대신:
  1) customer_name이 주어지면 "* {customer_name}" 과 정확히 일치하는 줄만 고객으로 판단
     (가장 정확함 - 폼에서 닉네임을 받아서 넘겨줄 것을 권장).
  2) 안 주어졌으면, 여러 번 반복해서 등장하는 "* " 다음 줄을 고객 이름으로 추정한다
     (실제 대화에서 고객 이름은 보통 여러 번 반복되지만 상담원 메시지의 첫 줄은
     매번 다른 문장이라 반복되지 않는다는 점을 이용한 추정 - 완벽하지 않음).
"""
import re
from collections import Counter

_TIME_RE = re.compile(r"^(읽음)?(오전|오후)\s*\d{1,2}:\d{2}$")


def _split_blocks(raw_text):
    lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    n = len(lines)
    blocks = []  # (first_line, body_lines)
    i = 0
    while i < n:
        line = lines[i]
        if line.startswith("* "):
            first_line = line[2:]
            i += 1
            body_lines = []
            while i < n and not _TIME_RE.match(lines[i].strip()):
                body_lines.append(lines[i])
                i += 1
            if i < n:
                i += 1  # 시각 줄 버림
            blocks.append((first_line, body_lines))
        else:
            i += 1
    return blocks


def _guess_customer_name(blocks):
    counts = Counter(fl.strip() for fl, _ in blocks if fl.strip())
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
    for first_line, body_lines in blocks:
        is_customer = name is not None and first_line.strip() == name
        full = body_lines if is_customer else ([first_line] + body_lines)
        while full and not full[0].strip():
            full.pop(0)
        while full and not full[-1].strip():
            full.pop()
        body = "\n".join(full).strip()
        if body:
            role = "고객" if is_customer else "상담원"
            messages.append(f"{role}: {body}")
    return "\n\n".join(messages)
