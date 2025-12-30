# ==========================================================
# TK 엘리베이터 통합 기술지원 AI
# OCR 미사용 / 회로도 텍스트 설명 기반
# 모바일 · Cloud 완전 대응
# ==========================================================

import streamlit as st
from openai import OpenAI
import os
import fitz
import re
import math

# ==========================================================
# OpenAI
# ==========================================================
client = OpenAI()

# ==========================================================
# 메뉴얼 로딩 (PDF + TXT + MD)
# ==========================================================
@st.cache_data(show_spinner=True)
def load_manual_chunks():
    manuals_dir = "manuals"
    chunks = []

    if not os.path.exists(manuals_dir):
        return chunks

    for file in os.listdir(manuals_dir):
        path = os.path.join(manuals_dir, file)

        # PDF (텍스트만)
        if file.lower().endswith(".pdf"):
            doc = fitz.open(path)
            for page_no, page in enumerate(doc, start=1):
                text = page.get_text().strip()
                if not text:
                    continue

                paragraphs = [
                    p.strip()
                    for p in text.split("\n\n")
                    if len(p.strip()) > 40
                ]

                for para in paragraphs:
                    chunks.append({
                        "file": file,
                        "page": page_no,
                        "text": para
                    })

        # TXT / MD (회로도 설명용)
        elif file.lower().endswith((".txt", ".md")):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            paragraphs = [
                p.strip()
                for p in content.split("\n\n")
                if len(p.strip()) > 30
            ]

            for para in paragraphs:
                chunks.append({
                    "file": file,
                    "page": "N/A",
                    "text": para
                })

    return chunks

MANUAL_CHUNKS = load_manual_chunks()

# ==========================================================
# 질문 ↔ 문단 유사도
# ==========================================================
def similarity(q, t):
    q_set = set(re.findall(r"[a-zA-Z0-9가-힣]+", q.lower()))
    t_set = set(re.findall(r"[a-zA-Z0-9가-힣]+", t.lower()))
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
✔ OCR 미사용  
✔ 회로도 설명 텍스트 지원  
✔ 모바일 5G/LTE 사용 가능  
✔ 추측 금지
""")

question = st.text_input("고장 증상 또는 질문을 입력하세요")

# ==========================================================
# 질문 처리
# ==========================================================
if st.button("질문하기") and question:
    if not MANUAL_CHUNKS:
        st.error("메뉴얼 데이터를 불러오지 못했습니다.")
    else:
        contexts = retrieve_context(question)

        if not contexts:
            st.warning("메뉴얼 기준 확인 불가")
        else:
            context_text = ""
            for c in contexts:
                context_text += f"\n[{c['file']} - {c['page']}]\n{c['text']}\n"

            response = client.responses.create(
                model="gpt-4.1-mini",
                input=[
                    {
                        "role": "system",
                        "content": f"""
너는 TK 엘리베이터 현장 기술지원 AI다.

규칙:
- 메뉴얼/회로 설명 파일에 있는 내용만 답한다
- 추측, 일반론, 경험담 생성 금지
- 없으면 "메뉴얼 기준 확인 불가"라고 말한다
- 점검 절차는 단계별로 제시
- 안전 관련 내용은 반드시 주의 문구 포함

[참조 문서]
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
