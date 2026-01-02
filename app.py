# ==========================================================
# ELAI (Elevator Logic AI)
# 메뉴얼 + 고장이력 기반 추측 강화
# 비밀번호 보호 / 모바일 · 앱 스타일 완전 대응
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
# 🔐 비밀번호 설정
# ==========================================================
APP_PASSWORD = os.getenv("ELAI_PASSWORD", "1234")  # 배포 시 환경변수 권장

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
.login-box {
    max-width: 360px;
    margin: auto;
    padding: 2.5rem;
    border-radius: 18px;
    background: #111827;
    box-shadow: 0 20px 40px rgba(0,0,0,0.4);
    text-align: center;
}
.login-title {
    font-size: 1.8rem;
    font-weight: 700;
    margin-bottom: 0.3rem;
}
.login-sub {
    color: #9CA3AF;
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
}
</style>
""", unsafe_allow_html=True)

# PWA
st.markdown('<link rel="manifest" href="/static/manifest.json">', unsafe_allow_html=True)

# ==========================================================
# 🔐 로그인 UI
# ==========================================================
def login_ui():
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.markdown('<div class="login-title">ELAI</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-sub">Elevator Logic AI</div>', unsafe_allow_html=True)

    pwd = st.text_input(
        "비밀번호",
        type="password",
        placeholder="Access Key",
        label_visibility="collapsed"
    )

    if st.button("ENTER", use_container_width=True):
        if pwd == APP_PASSWORD:
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("접근 권한이 없습니다")

    st.markdown('</div>', unsafe_allow_html=True)

# 인증 체크
if "auth" not in st.session_state:
    login_ui()
    st.stop()

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
# 유사도
# ==========================================================
def similarity(a, b):
    a_set = set(re.findall(r"[a-zA-Z0-9가-힣]+", a.lower()))
    b_set = set(re.findall(r"[a-zA-Z0-9가-힣]+", b.lower()))
    if not a_set or not b_set:
        return 0
    return len(a_set & b_set) / math.sqrt(len(a_set) * len(b_set))

def retrieve_manual_context(q):
    scored = [(similarity(q, c["text"]), c) for c in MANUAL_CHUNKS]
    scored = [x for x in scored if x[0] > 0]
    scored.sort(reverse=True, key=lambda x: x[0])
    return [c for _, c in scored[:5]]

def retrieve_failure_context(q):
    scored = [(similarity(q, h.get("고장증상", "")), h) for h in FAILURE_HISTORY]
    scored = [x for x in scored if x[0] > 0]
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

    manual_text = "\n".join(
        f"[{c['file']} - {c['page']}]\n{c['text']}"
        for c in manual_ctx
    )

    failure_text = "\n".join(
        f"- 고장증상: {h.get('고장증상')}\n- 에러코드: {h.get('에러코드')}\n- 처리내용: {h.get('처리내용')}"
        for h in failure_ctx
    )

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": f"""
너는 엘리베이터 현장 기술지원 AI다.

출력 규칙:
1. [메뉴얼 기준 설명]
2. [고장이력 기반 AI 추측 ⚠️]
3. ⚠️ 본 추측은 참고용이며 최종 책임은 현장 기사에게 있음

[메뉴얼]
{manual_text}

[고장이력]
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

    st.success(response.output_text)
