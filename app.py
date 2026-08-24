# -*- coding: utf-8 -*-
"""
Vercel용 단일 Flask 앱.

"/"       -> index.html 그대로 서빙
"/api/data" -> 브라우저가 대시보드를 열 때마다 구글시트에서 그 순간의 최신
              데이터를 읽어와 반환 (cs_data.json 같은 정적 파일이나 수동
              push가 필요 없어짐 - 예전 export_dashboard.py 로직을 옮겨옴)

필요한 Vercel 환경변수 3개:
  GOOGLE_SERVICE_ACCOUNT_JSON -> service_account.json 파일 내용 전체(중괄호 포함)
  SHEET_ID                    -> 구글시트 ID
  DASHBOARD_PASSWORD          -> 대시보드 접속 비밀번호
"""
import os
import re
import json

from flask import Flask, Response, request, send_file
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

CS_TABS = ["카페24_CS", "네이버_CS", "채팅상담_CS"]


def mask_pii(text):
    if not text:
        return text
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[이메일 가림]", text)
    text = re.sub(r"0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}", "[연락처 가림]", text)
    text = re.sub(r"\b\d{8,}\b", "[주문번호 가림]", text)
    return text


def normalize_product(text):
    if not text:
        return "미분류"
    if "케이블" in text:
        return "오리지널 케이블"
    m = re.search(r"몰입의\s*방\s*(오리지널\s*V2|오리지널|프로|미니)", text)
    if not m:
        return "미분류"
    variant = m.group(1).replace(" ", "")
    return {
        "오리지널V2": "오리지널 V2",
        "오리지널": "오리지널",
        "프로": "프로",
        "미니": "미니",
    }[variant]


CLASSIFY_RULES = [
    ("배송문의", "배송문의", [r"배송", r"언제\s?(와|오)", r"도착", r"택배", r"운송장", r"출고", r"상품\s?준비중", r"발송"]),

    ("기타 문의", "비상 해제 요청", [
        r"지금\s?열어주세요", r"급하게\s?열어", r"당장\s?열어", r"열어달라", r"빨리\s?열어",
        r"급한.{0,15}(열|해제)", r"급해.{0,15}(열|해제)", r"갇혀", r"지금\s?당장.{0,10}(열|해제)",
    ]),

    ("제품 불량", "제품 파손/마감 문제", [
        r"파손", r"깨(지|짐|졌|져)", r"부러지", r"기스", r"흠집", r"스크래치",
        r"금이\s?가", r"떨어[뜨트]려", r"덜그덕", r"덜컹", r"벌어져", r"마감이?\s?(안|불량)",
        r"안\s?닫혀", r"안닫혀",
    ]),
    ("제품 불량", "잘 열림", [
        r"쉽게\s?열려", r"그냥\s?열려", r"너무\s?쉽게\s?열", r"잠금이?\s?풀",
        r"(흔들|흔드)[니는면]?.{0,15}(열리|열림|빠진)", r"뒤집.{0,15}(열리|열림)", r"위아래로\s?흔들",
        r"치[니면].{0,15}열", r"잠겼는데.{0,5}(그냥|열)", r"톡\s?치",
        r"떨어[뜨트]리.{0,10}(열리|열림)", r"남았는데.{0,10}열\s?수\s?있",
    ]),
    ("제품 불량", "잠금 안 됨", [r"잠금이?\s?안", r"잠기지\s?않", r"안\s?잠기", r"안잠기", r"잠김이?\s?안", r"경첩", r"잠금\s?기능이\s?작동하지", r"저절로\s?열려", r"자꾸\s?열려"]),
    ("제품 불량", "안열림", [
        r"안\s?열려", r"안열려", r"열리지\s?않", r"열리지가\s?않", r"열\s?수\s?없", r"열\s?수가\s?없",
        r"못\s?열", r"반응이?\s?없", r"반응을?\s?안",
    ]),
    ("제품 불량", "충전 안 됨", [r"충전.{0,10}안\s?(되|돼|된)", r"반품요청"]),
    ("제품 불량", "버튼 인식 문제", [r"버튼.{0,5}안\s?눌", r"버튼.{0,5}눌리지", r"버튼\s?눌러도", r"버튼이\s?망가"]),
    ("제품 불량", "LED창 불량", [r"led", r"불빛.{0,3}안"]),
    ("제품 불량", "회로 문제", [r"회로", r"모터\s?소리", r"작동\s?소리만", r"먹통", r"고장", r"휠.{0,5}(동작|안)"]),

    ("사용 방법", "비상 해제 가능 여부", [
        r"비상\s?해제", r"긴급해제", r"비상열림", r"강제잠금", r"강제\s?해제", r"강제\s?오픈",
        r"해제기능", r"해제할\s?수\s?있는", r"여는법을?\s?알아", r"초기화가?\s?되", r"초기화\s?할",
        r"잠금을?\s?풀어야", r"부셔야\s?되나요", r"리셋\s?방법", r"충격을?\s?주면",
        r"시간.{0,10}(잘못|착오)", r"설정.{0,10}초기화",
    ]),
    ("사용 방법", "무음 모드", [r"무음", r"소리\s?안나게", r"소리가?\s?안나", r"알람\s?소리"]),
    ("사용 방법", "충전 방법", [
        r"충전.{0,10}(안되|안돼|되는지|얼마나|불\s?켜져|표시)", r"충전단자", r"충전\s?꽂아도",
        r"충전기로는", r"c-?type", r"씨타입", r"완충",
    ]),
    ("사용 방법", "제품 사이즈, 기종 문의", [r"아이폰", r"갤럭시", r"폴드", r"핸드폰\s?크기", r"사용가능한가요", r"들어가나요", r"충전타입", r"기종"]),
    ("사용 방법", "오픈 방법", [r"여는\s?방법", r"여는법", r"어떻게\s?열어", r"설정시\s?여는", r"개방\s?방법", r"열수\s?있는\s?방법", r"여려면", r"구멍이\s?리셋"]),
    ("사용 방법", "케이블 사용법", [
        r"케이블.{0,10}(연결|꽂|사용법|사용\s?방법|규격)", r"(연결|꽂|사용법|사용\s?방법).{0,10}케이블",
        r"usb\s?선.{0,10}(연결|꽂|사용)", r"충전선이?\s?안에",
    ]),

    ("기타 문의", "AS 여부", [r"as\s?가능", r"a\s?/\s?s", r"수리\s?가능", r"수리\s?문의", r"수리\s?되"]),
    ("기타 문의", "케이블 구매안내", [r"케이블만?\s?(따로)?\s?구매", r"케이블.{0,5}(판매|팔아|어디서)"]),
]


def classify_inquiry(text):
    if not text:
        return ("기타 문의", "기타")
    lowered = text.lower()
    for major, minor, patterns in CLASSIFY_RULES:
        for pat in patterns:
            if re.search(pat, lowered):
                return (major, minor)
    return ("기타 문의", "기타")


def fetch_records():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(os.environ["SHEET_ID"])

    all_records = []
    for tab_name in CS_TABS:
        try:
            tab = spreadsheet.worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            continue
        values = tab.get_all_values()
        if not values:
            continue
        headers = values[0]
        records = [dict(zip(headers, row)) for row in values[1:] if row]
        for r in records:
            if "고객문의" in r:
                r["고객문의"] = mask_pii(r["고객문의"])
            if "답변내용" in r:
                r["답변내용"] = mask_pii(r["답변내용"])
            if "제품" in r:
                r["제품"] = normalize_product(r["제품"])
            major, minor = classify_inquiry(r.get("고객문의", ""))
            r["문제유형"] = major
            r["소분류"] = minor
        all_records.extend(records)
    return all_records


@app.route("/")
def index():
    return send_file("index.html")


@app.route("/api/data")
def api_data():
    pw = request.headers.get("X-Dashboard-Password", "")
    if pw != os.environ.get("DASHBOARD_PASSWORD"):
        return Response(json.dumps({"error": "unauthorized"}), status=401, mimetype="application/json")

    try:
        records = fetch_records()
    except Exception as e:
        return Response(json.dumps({"error": str(e)}), status=500, mimetype="application/json")

    resp = Response(json.dumps(records, ensure_ascii=False), mimetype="application/json")
    resp.headers["Cache-Control"] = "no-store"
    return resp
