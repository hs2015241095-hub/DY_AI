# ==========================================================
# ELAI (Elevator Logic AI)
# 메뉴얼 + 고장이력 기반 추측 강화
# 모바일 / 앱 스타일 완전 대응
# ==========================================================

import streamlit as st
from openai import OpenAI
import os
import fitz
import re
import math
import csv
from PIL import Image

# ==========================================================
# 페이지 설정
# ==========================================================
st.set_page_config(
    page_title="ELAI",
    page_icon="static/favicon.png",
    layout="wide"
)

# ==========================================================
# 앱 스타일 (완전 앱 느낌)
# ==========================================================
st.markdown("""
<style>
html, body, [class*="css"]  {
    background-color: #0f1117;
    color: #e6e6e6;
    font-family: Pretendard, sans-serif;
}
input {
    background-color: #1c1f26 !important;
    color: white !important;
    border-radius: 8px !important;
}
button {
    background-color: #2563eb !important;
    color: white !important;
    border-radius: 10px !important;
    height: 50px;
    font-size: 18px;
}
button:hover {
    background-color: #1d4ed8 !important;
}
</style>
""", unsafe_allow_html=True)

# PWA
st.markdown('<link rel="manifest" href="/static/manifest.json">', unsafe_allow_html=True)

# ==========================================================
# OpenAI
# ==========================================================
client = OpenAI()

# ==========================================================
# 메뉴얼 로딩
# ==========================================================
@st.cache_data(show_spinner=True)
def load_manual_chunks():
    chunks = []
    if not os.path.exists("manuals"):
        return chunks

    for file in os.listdir("manuals"):
        if not file.lower().endswith(".pdf"):
            continue

        doc = fitz.open(os.path.join("manuals", file))
        for page_no, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if not text:
                continue

            for para in text.split("\n\n"):
                if len(para.strip()) > 40:
                    chunks.append({
                        "file": file,
                        "page": page_no,
                        "text": para.strip()
                    })
    return chunks

MANUAL_CHUNKS = load_manual_chunks()

# ==========================================================
# 고장이력 로딩 (CSV)
# ==========================================================
@st.cache_data(show_spinner=False)
def load_failure_history():
    history = []
    if not os.path.exists("failure_history.csv"):
        return history

    with open("failure_history.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            history.append(row)
    return history

FAILURE_HISTORY = load_failure_history()

# ==========================================================
# 유사도
# ==========================================================
def similarity(a, b):
    a_set = set(re.findall(r"[a-zA-Z0-9가-힣]+", a.lower()))
    b_set = set(re.findall(r"[a-zA-Z0-9가-힣]+", b.lower()))
    if not a_set or not b_set:
        return 0
    return len(a_set & b_set) / math.sqrt(len(a_set) * len(b_set))

def retrieve_manual_context(question):
    scored = []
    for c in MANUAL_CHUNKS:
        s = similarity(question, c["text"])
        if s > 0:
            scored.append((s, c))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [c for _, c in scored[:5]]

def retrieve_failure_context(question):
    scored = []
    for h in FAILURE_HISTORY:
        s = similarity(question, h.get("고장증상", ""))
        if s > 0:
            scored.append((s, h))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [h for _, h in scored[:3]]

# ==========================================================
# UI
# ==========================================================
st.title("ELAI")

question = st.text_input("고장증상 또는 질문을 입력하세요")

uploaded_image = st.file_uploader(
    "회로도 이미지 첨부 (선택 / 참고용)",
    type=["png", "jpg", "jpeg"]
)

# ==========================================================
# 실행
# ==========================================================
if st.button("ENTER"):

    manual_ctx = retrieve_manual_context(question)
    failure_ctx = retrieve_failure_context(question)

    if not manual_ctx and not failure_ctx:
        st.warning("메뉴얼 및 고장이력 기준 확인 불가")
        st.stop()

    manual_text = ""
    for c in manual_ctx:
        manual_text += f"\n[{c['file']} - {c['page']}]\n{c['text']}\n"

    failure_text = ""
    for h in failure_ctx:
        failure_text += f"""
- 고장증상: {h.get('고장증상')}
- 에러코드: {h.get('에러코드')}
- 처리내용: {h.get('처리내용')}
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": f"""
너는 엘리베이터 현장 기술지원 AI다.

출력 규칙:
1. [메뉴얼 기준 설명]
2. [고장이력 기반 AI 추측 ⚠️] (있을 때만)
3. 책임 경고 문구 필수

[메뉴얼 자료]
{manual_text}

[고장이력 자료]
{failure_text}
"""
            },
            {
                "role": "user",
                "content": question
            }
        ]
    )

    if uploaded_image:
        st.image(Image.open(uploaded_image), caption="첨부 회로도 (참고용)", use_container_width=True)

    output = response.output_text

    if "[고장이력 기반 AI 추측" in output:
        base, guess = output.split("[고장이력 기반 AI 추측")
        st.success(base)
        st.markdown(
            f"<span style='color:#ff4d4f'>[고장이력 기반 AI 추측{guess}</span>",
            unsafe_allow_html=True
        )
    else:
        st.success(output)
