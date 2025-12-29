# ==========================================================
# TK 엘리베이터 통합 기술지원 AI (사내 전용)
# 메뉴얼 + 회로도 + OCR + 고장이력 학습 + PWA
# ==========================================================

import streamlit as st
from openai import OpenAI
import os, io, re, math, csv
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
from datetime import datetime

# ==========================================================
# 0️⃣ 기본 설정
# ==========================================================
APP_PASSWORD = "1234"   # 🔐 사내 비밀번호
FAILURE_LOG = "failure_logs.csv"

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
client = OpenAI()

# ==========================================================
# 1️⃣ PWA 설정 (홈 화면 아이콘)
# ==========================================================
st.set_page_config(
    page_title="TK Elevator AI",
    page_icon="🛠️",
    layout="wide"
)

st.markdown("""
<link rel="manifest" href="data:application/json,{
  \\"name\\": \\"TK Elevator AI\\",
  \\"short_name\\": \\"TK-AI\\",
  \\"start_url\\": \\".\\",
  \\"display\\": \\"standalone\\",
  \\"background_color\\": \\"#ffffff\\",
  \\"theme_color\\": \\"#00205b\\"
}">
""", unsafe_allow_html=True)

# ==========================================================
# 2️⃣ 로그인
# ==========================================================
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 동양 E&i")
    pw = st.text_input("비밀번호 입력", type="password")
    if st.button("접속"):
        if pw == APP_PASSWORD:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("비밀번호 오류")
    st.stop()

# ==========================================================
# 3️⃣ 최근 질문 기록
# ==========================================================
if "history" not in st.session_state:
    st.session_state.history = []

# ==========================================================
# 4️⃣ 메뉴얼 로드 (텍스트 + OCR → 문단)
# ==========================================================
@st.cache_data(show_spinner=True)
def load_manual_chunks():
    chunks = []
    manuals_dir = "manuals"

    if not os.path.exists(manuals_dir):
        return chunks

    for pdf in os.listdir(manuals_dir):
        if not pdf.lower().endswith(".pdf"):
            continue

        doc = fitz.open(os.path.join(manuals_dir, pdf))

        for page_no, page in enumerate(doc, start=1):
            text = page.get_text().strip()

            if not text:
                pix = page.get_pixmap(dpi=300)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text = pytesseract.image_to_string(img, lang="eng", config="--psm 6")

            paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 40]

            for para in paragraphs:
                chunks.append({
                    "file": pdf,
                    "page": page_no,
                    "text": para
                })

    return chunks

MANUAL_CHUNKS = load_manual_chunks()

# ==========================================================
# 5️⃣ 사내 고장이력 CSV 로드
# ==========================================================
def load_failure_logs():
    logs = []
    if not os.path.exists(FAILURE_LOG):
        return logs

    with open(FAILURE_LOG, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        logs = list(reader)
    return logs

def save_failure_log(symptom, error_code, answer):
    exists = os.path.exists(FAILURE_LOG)
    with open(FAILURE_LOG, "a", newline="", encoding="utf-8") as f:
        fieldnames = ["time", "symptom", "error_code", "answer"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({
            "time": datetime.now().isoformat(),
            "symptom": symptom,
            "error_code": error_code,
            "answer": answer
        })

FAILURE_LOGS = load_failure_logs()

# ==========================================================
# 6️⃣ 문단 유사도 검색
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

def retrieve_failure_context(question):
    related = []
    for log in FAILURE_LOGS:
        if similarity(question, log["symptom"]) > 0.2:
            related.append(log)
    return related[:3]

# ==========================================================
# 7️⃣ UI
# ==========================================================
st.title("🛠️ TK 엘리베이터 통합 기술지원 AI")

with st.sidebar:
    st.subheader("📌 최근 질문")
    for q in st.session_state.history[:10]:
        st.markdown(f"- {q}")

    if st.button("로그아웃"):
        st.session_state.auth = False
        st.rerun()

question = st.text_input("고장 증상 / 에러코드 / 질문 입력")

error_code = st.text_input("에러코드 (선택)")

# ==========================================================
# 8️⃣ 질문 처리
# ==========================================================
if st.button("질문하기") and question:
    st.session_state.history.insert(0, question)
    st.session_state.history = st.session_state.history[:10]

    manual_ctx = retrieve_context(question)
    failure_ctx = retrieve_failure_context(question)

    context_text = ""
    for c in manual_ctx:
        context_text += f"\n[메뉴얼 {c['file']} p.{c['page']}]\n{c['text']}\n"

    failure_text = ""
    for f in failure_ctx:
        failure_text += f"\n[과거사례]\n증상: {f['symptom']}\n에러: {f['error_code']}\n조치: {f['answer']}\n"

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": f"""
너는 TK 엘리베이터 현장 기술지원 AI다.

규칙:
- 메뉴얼 + 사내 고장이력만 참고
- 추측 금지
- 안전 최우선
- 단계별 점검 제시
- 없으면 '확인 불가' 명시

[메뉴얼]
{context_text}

[사내 고장이력]
{failure_text}
"""
            },
            {"role": "user", "content": question}
        ]
    )

    answer = response.output_text
    st.success(answer)

    save_failure_log(question, error_code, answer)
