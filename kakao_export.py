# -*- coding: utf-8 -*-
"""
카카오 비즈니스 채널 콘솔에서 "엑셀로 내보내기" 한 대화 파일을 파싱한다.

같은 "엑셀로 내보내기" 버튼인데도 실제로는 .xlsx와 .csv 두 형식으로 다 나올 수 있어서
(실제 관찰됨) 둘 다 지원한다. 컬럼은 공통으로 DATE, USER, MESSAGE.
USER가 채널명(에이전트)이면 상담원 메시지, 그 외엔 고객 메시지로 취급한다.

xlsx에서 읽어온 셀 값에 엑셀 XML 이스케이프가 덜 풀린 "_x000D_"(캐리지리턴) 잔재가
섞여 있는 경우가 있어 제거하고, "지금은 ~ 채팅 가능한 시간이 아닙니다" 같은 자동 응답
문구는 실제 상담 내용이 아니라서 걸러낸다.
"""
import csv
import io
from datetime import datetime

import openpyxl

AGENT_NAME = "더비랩"
_AUTO_REPLY_PATTERNS = [
    "채팅 운영시간 안내",
    "채팅 가능한 시간이 아닙니다",
]


def _clean(text):
    if not text:
        return ""
    return str(text).replace("_x000D_", "").strip()


def _is_auto_reply(text):
    return any(p in text for p in _AUTO_REPLY_PATTERNS)


def _parse_date(date_val):
    """xlsx는 datetime 객체, csv는 "YYYY-MM-DD HH:MM:SS" 문자열로 온다."""
    if date_val is None:
        return None
    if isinstance(date_val, str):
        try:
            return datetime.strptime(date_val.strip(), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    return date_val


def _extract_rows_xlsx(file_bytes):
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    for name in wb.sheetnames:
        ws = wb[name]
        header = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        if header[:3] == ["DATE", "USER", "MESSAGE"]:
            return list(ws.iter_rows(min_row=2, values_only=True))
    return None


def _extract_rows_csv(file_bytes):
    text = file_bytes.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or rows[0][:3] != ["DATE", "USER", "MESSAGE"]:
        return None
    return rows[1:]


def parse_kakao_export(file_bytes):
    """반환: (대화 전문(문자열), 상담 시작일 "YYYY-MM-DD" 또는 None) 튜플.
    대화 전문은 사람이 읽기 좋은 "역할: 메시지" 형태로 합침.
    상담 시작일은 대화의 첫 메시지에 찍힌 DATE 값 기준(업로드 시점이 아님).
    파싱 실패/빈 파일이면 ("", None)."""
    try:
        rows = _extract_rows_xlsx(file_bytes)
    except Exception:
        rows = None
    if rows is None:
        rows = _extract_rows_csv(file_bytes)
    if not rows:
        return "", None

    lines = []
    start_date = None
    for row in rows:
        if not row or len(row) < 3:
            continue
        date_val, user, message = _parse_date(row[0]), _clean(row[1]), _clean(row[2])
        if not message or _is_auto_reply(message):
            continue
        role = "상담원" if user == AGENT_NAME else "고객"
        time_str = ""
        if date_val is not None:
            if start_date is None:
                start_date = date_val.strftime("%Y-%m-%d")
            time_str = date_val.strftime("%m/%d %H:%M")
        prefix = f"[{time_str}] " if time_str else ""
        lines.append(f"{prefix}{role}: {message}")

    return "\n".join(lines), start_date
