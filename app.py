@st.cache_data(show_spinner=True)
def load_manual_chunks():
    chunks = []

    if not os.path.exists("manuals"):
        st.error("❌ manuals 폴더가 존재하지 않습니다.")
        return chunks

    files = os.listdir("manuals")
    if not files:
        st.error("❌ manuals 폴더는 있으나 파일이 없습니다.")
        return chunks

    st.info(f"📂 manuals 폴더 파일 목록: {files}")

    for file in files:
        if not file.lower().endswith(".pdf"):
            continue

        path = os.path.join("manuals", file)

        try:
            doc = fitz.open(path)
        except Exception as e:
            st.error(f"❌ PDF 열기 실패: {file} / {e}")
            continue

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

    st.success(f"✅ 메뉴얼 문단 로딩 완료: {len(chunks)}개")
    return chunks
