# -*- coding: utf-8 -*-
"""
네이버 커머스 API로 고객문의(주문 관련)/상품문의(Q&A)에 실제로 답변을 등록한다.

**이 파일의 함수는 사람이 대시보드에서 "네이버에 답변 전송" 버튼을 눌렀을 때만
호출된다** (app.py의 /api/send-naver-answer) - 실제로 고객에게 노출되는 답변을
올리는 동작이라, 절대 사람 확인 없이 자동으로 호출하면 안 됨.

인증은 cs-automation의 naver_sync_full.py(문의 "조회"에 씀)와 완전히 동일한 방식
(HMAC 서명, client_credentials)이고 CLIENT_ID도 같음 - 다만 "조회" 권한과
"답변 등록" 권한은 네이버 커머스 API 센터에서 별도로 부여되는 경우가 있어서, 이
기능이 실제로 성공하는지는 대시보드에서 처음 "전송"을 눌러봐야 확인된다
(2026-09-22 최초 구현, 아직 실제 성공 사례로 검증 못 함). 만약 401/403류 에러가
나면 네이버 커머스 API 센터(https://apicenter.commerce.naver.com)에서 이 앱에
문의 답변 등록 권한이 켜져 있는지부터 확인할 것.

필요한 환경변수(Vercel): NAVER_CLIENT_SECRET (cs-automation의 secrets.local.ps1에
있는 값과 동일한 걸 그대로 씀).

엔드포인트 출처: 네이버 커머스 API 공식 기술지원(commerce-api-naver/commerce-api)
답변을 참고함(2026-09-22) - 상품문의(qnas) 쪽 답변 필드명("commentContent")은
공식 답변에 명시되어 있었고, 고객문의(inquiries) 쪽 답변 필드명("answerContent")은
조회 응답 필드명과 통일했을 거라는 추정임(실제 성공/실패로 확정 필요).
"""
import os
import time
import base64
import bcrypt
import requests

CLIENT_ID = "56VpDMqHtQ0dJfwdZ2ail7"


def get_access_token():
    client_secret = os.environ["NAVER_CLIENT_SECRET"]
    timestamp = str(int(time.time() * 1000))
    password = f"{CLIENT_ID}_{timestamp}"
    hashed = bcrypt.hashpw(password.encode("utf-8"), client_secret.encode("utf-8"))
    client_secret_sign = base64.b64encode(hashed).decode("utf-8")
    url = "https://api.commerce.naver.com/external/v1/oauth2/token"
    data = {
        "client_id": CLIENT_ID, "timestamp": timestamp,
        "client_secret_sign": client_secret_sign,
        "grant_type": "client_credentials", "type": "SELF",
    }
    headers = {"content-type": "application/x-www-form-urlencoded"}
    resp = requests.post(url, data=data, headers=headers)
    resp.raise_for_status()
    return resp.json()["access_token"]


def answer_customer_inquiry(access_token, inquiry_no, answer_text):
    """고객문의(주문 관련) 답변 등록. POST /v1/pay-merchant/inquiries/{inquiryNo}/answer"""
    url = f"https://api.commerce.naver.com/external/v1/pay-merchant/inquiries/{inquiry_no}/answer"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json={"answerContent": answer_text})
    resp.raise_for_status()
    return resp.json() if resp.text else {}


def answer_product_qna(access_token, question_id, answer_text):
    """상품문의(Q&A) 답변 등록. PUT /v1/contents/qnas/{id}"""
    url = f"https://api.commerce.naver.com/external/v1/contents/qnas/{question_id}"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    resp = requests.put(url, headers=headers, json={"commentContent": answer_text})
    resp.raise_for_status()
    return resp.json() if resp.text else {}


def send_answer(inquiry_id, answer_text):
    """문의ID 접두어(naver_sync_full.py가 붙이는 "NV-고객-"/"NV-상품-")로 어느 API를
    쓸지 정해서 답변을 등록한다."""
    access_token = get_access_token()
    if inquiry_id.startswith("NV-고객-"):
        return answer_customer_inquiry(access_token, inquiry_id[len("NV-고객-"):], answer_text)
    if inquiry_id.startswith("NV-상품-"):
        return answer_product_qna(access_token, inquiry_id[len("NV-상품-"):], answer_text)
    raise ValueError(f"답변 등록을 지원하지 않는 문의ID예요: {inquiry_id}")
