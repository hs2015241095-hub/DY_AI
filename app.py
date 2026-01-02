# ==========================================================
# ELAI (Elevator Logic AI)
# 메뉴얼 기반 기술지원 AI
# 모바일 / 앱 스타일 대응
# ==========================================================

import streamlit as st
from openai import OpenAI
import os
import fitz
import re
import math
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

# PWA manifest
st.markdown('<link rel="manifest" href="/static/manifest.json">', unsafe_allow_html=True)

# ==========================================================
# OpenAI
# ==========================================================
client = OpenAI()

# ==========================================================
# 메뉴얼 로딩 (PDF 텍스트만)
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
                para = para.strip()
                if len(para) > 40:
                    chunks.append({
                        "file": file,
                        "page": page_no,
                        "text": para
                    })
    return chunks

MANUAL_CHUNKS = load_manual_chunks()

# ==========================================================
# 유사도 계산
# ==========================================================
def similarity(a, b):
    a_set = set(re.findall(r"[a-zA-Z0-9가-힣]+", a.lower()))
    b_set = set(re.findall(r"[a-zA-Z0-9가-힣]+", b.lower()))
    if not a_set or not b_set:
        return 0
    return len(a_set & b_set) / math.sqrt(len(a_set) * len(b_set))

def retrieve_manual_context(question, top_k=5):
    scored = []
    for c in MANUAL_CHUNKS:
        s = similarity(question, c["text"])
        if s > 0:
            scored.append((s, c))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [c for _, c in scored[:top_k]]

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

    if not question:
        st.warning("질문을 입력하세요.")
        st.stop()

    if not MANUAL_CHUNKS:
        st.error("메뉴얼 데이터를 불러오지 못했습니다.")
        st.stop()

    contexts = retrieve_manual_context(question)

    if not contexts:
        st.warning("메뉴얼 기준 확인 불가")
        st.stop()

    manual_text = ""
    for c in contexts:
        manual_text += f"\n[{c['file']} - page {c['page']}]\n{c['text']}\n"

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": f"""
너는 엘리베이터 현장 기술지원 AI다.

규칙:
- 메뉴얼 텍스트에 있는 내용만 설명
- 추측, 경험담, 일반론 금지
- 이미지에서 회로 판독 금지
- 메뉴얼에 없으면 "메뉴얼 기준 확인 불가"라고 명시
- 단발성 질문 (기억 없음)

[메뉴얼 발췌]
{manual_text}
"""
            },
            {
                "role": "user",
                "content": question
            }
        ]
    )

    if uploaded_image:
        st.image(
            Image.open(uploaded_image),
            caption="첨부 회로도 (참고용)",
            use_container_width=True
        )

    st.success(response.output_text)
