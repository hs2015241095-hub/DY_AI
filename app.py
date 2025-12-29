# ==========================================================
# TK 엘리베이터 통합 기술지원 AI
# 메뉴얼 기반 / OCR 안전 비활성화 (Streamlit Cloud 대응)
# ==========================================================

import streamlit as st
from openai import OpenAI
import os
import fitz  # PyMuPDF
from PIL import Image
import io
import re
import math

# ==========================================================
# OpenAI
# ==========================================================
client = OpenAI()

# ==========================================================
# PDF → 페이지 → 문단 단위 로드 (텍스트만 사용)
# ==========================================================
@st.cache_data(show_spinner=True)
def load_manual_chunks():
    manuals_dir = "manuals"
    chunks = []

    if not os.path.exists(manuals_dir):
        return chunks

    for pdf in os.listdir(manuals_dir):
        if not pdf.lower().endswith(".pdf"):
            continue

        doc = fitz.open(os.path.join(manuals_dir, pdf))

        for page_no, page in enumerate(doc, start=1):
            text = page.get_text().strip()

            # 🔴 OCR 완전 비활성화 (Cloud 안정성)
            if not text:
                continue

            paragraphs = [
                p.strip()
                for p in text.split("\n\n")
                if len(p.strip()) > 40
            ]

            for para in paragraphs:
                chunks.append({
                    "file": pdf,
                    "page": page_no,
                    "text": para
                })

    return chunks

MANUAL_CHUNKS = load_manual_chunks()

# ==========================================================
# 질문 ↔ 문단 유사도 계산
# ==========================================================
def similarity(q, t):
    q_set = set(re.findall(r"[a-zA-Z0-9]+", q.lower()))
    t_set = set(re.findall(r"[a-zA-Z0-9]+", t.lower()))
    if not q_set or not t_set:
        return 0
    return len(q_set & t_set) / math.sqrt(len(q_set) * len(t_set))

def retrieve_context(question, top_k=6):
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
st.set_page_config("TK Elevator 기술지원 AI", layout="wide")
st.title("🛠️ TK 엘리베이터 통합 기술지원 AI")

st.markdown("""
✔ 메뉴얼 기반  
✔ 추측 금지  
✔ 텍스트 PDF 최적화  
✔ Streamlit Cloud 안정 버전
""")

question = st.text_input("고장 증상 또는 질문을 입력하세요")

# ==========================================================
# 질문 처리
# ==========================================================
if st.button("질문하기") and question:
    if not MANUAL_CHUNKS:
        st.error("메뉴얼에서 텍스트를 읽지 못했습니다.")
    else:
        contexts = retrieve_context(question)

        context_text = ""
        for c in contexts:
            context_text += f"\n[{c['file']} - page {c['page']}]\n{c['text']}\n"

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "system",
                    "content": f"""
너는 TK 엘리베이터 현장 기술지원 AI다.

규칙:
- 메뉴얼에 있는 내용만 설명한다
- 추측, 일반화, 임의 해석 금지
- 없으면 '메뉴얼 기준 확인 불가'라고 명시
- 점검은 단계별로 제시
- 안전 관련 내용은 반드시 주의 표시

[메뉴얼 발췌]
{context_text}
"""
                },
                {
                    "role": "user",
                    "content": question
                }
            ]
        )

        st.success(response.output_text)
