import streamlit as st
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image
import io
import hashlib
import pytesseract
from pdf2image import convert_from_bytes
import sqlite3
import threading
import uvicorn
import requests
import time
import json
import os

# ----------------- Backend Code -------------------

app = FastAPI(title="JACVS API")

DB_FILE = "mock_verification.db"

def init_db():
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE certificates (
                name TEXT PRIMARY KEY,
                roll_no TEXT,
                cert_id TEXT
            )
        ''')
        c.execute("INSERT INTO certificates VALUES (?, ?, ?)", ("John Doe", "RU12345", "RU/UG/2023/001"))
        c.execute("INSERT INTO certificates VALUES (?, ?, ?)", ("Jane Smith", "RU54321", "RU/PG/2023/002"))
        conn.commit()
        conn.close()

def query_db(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT roll_no, cert_id FROM certificates WHERE name=?", (name,))
    result = c.fetchone()
    conn.close()
    return result

def process_certificate_ocr(image: Image.Image):
    # Simple OCR using pytesseract; replace with your enhanced function
    text = pytesseract.image_to_string(image, lang='eng+hin')
    lines = text.split('\n')
    extracted_data = {
        "name": "",
        "roll_no": "",
        "cert_id": ""
    }
    for line in lines:
        if "Name:" in line:
            extracted_data["name"] = line.split("Name:")[-1].strip()
        elif "Roll No" in line:
            extracted_data["roll_no"] = line.split("Roll No")[-1].strip()
        elif "Certificate ID" in line:
            extracted_data["cert_id"] = line.split("Certificate ID")[-1].strip()
    ocr_confidence = 80  # Dummy confidence
    return {"extracted_data": extracted_data, "ocr_confidence": ocr_confidence, "full_text": text}

@app.post("/verify")
async def verify_certificate(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        if file.content_type.startswith('image/'):
            image = Image.open(io.BytesIO(contents))
        elif file.content_type == 'application/pdf':
            images = convert_from_bytes(contents)
            image = images[0] if images else None
        else:
            return JSONResponse(status_code=400, content={"error": "Unsupported file type"})
        if not image:
            return JSONResponse(status_code=400, content={"error": "No image extracted"})

        ocr_result = process_certificate_ocr(image)

        img_bytes = io.BytesIO()
        image.save(img_bytes, format='PNG')
        document_hash = hashlib.sha256(img_bytes.getvalue()).hexdigest()

        extracted_data = ocr_result.get('extracted_data', {})
        name = extracted_data.get('name', '').strip()
        roll_no = extracted_data.get('roll_no', '').strip()
        cert_id = extracted_data.get('cert_id', '').strip()

        db_result = query_db(name)

        anomalies = []
        confidence_score = ocr_result.get('ocr_confidence', 0)
        status = "Valid"
        recommendation = "Proceed with verification."

        if db_result:
            db_roll_no, db_cert_id = db_result
            if db_roll_no != roll_no or db_cert_id != cert_id:
                anomalies.append("Mismatch in Roll No or Certificate ID")
                status = "Caution"
                confidence_score = min(confidence_score, 60)
                recommendation = "Manual review recommended."
        else:
            anomalies.append("Name not found in records")
            status = "Forged"
            confidence_score = min(confidence_score, 30)
            recommendation = "Document appears invalid."

        if confidence_score < 70:
            anomalies.append("Low OCR confidence - blurry image?")

        result = {
            "status": status,
            "confidence_score": confidence_score,
            "recommendation": recommendation,
            "anomalies": anomalies,
            "extracted_data": extracted_data,
            "document_hash": document_hash,
            "full_text": ocr_result.get('full_text', '')
        }
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

def run_api():
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    server.run()

# ----------------- Frontend Code -------------------

def wait_for_api(url="http://127.0.0.1:8000/docs", timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url)
            if r.status_code == 200:
                return True
        except:
            time.sleep(1)
    return False

# Init DB once before app runs
init_db()

if 'api_thread' not in st.session_state:
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    st.session_state.api_thread = api_thread
    st.experimental_rerun()

st.set_page_config(page_title="JACVS Verifier", layout="wide")

st.title("🛡️ JACVS - Jharkhand Academic Credential Verification System")
st.markdown("Upload a certificate (PDF/JPG) for instant authenticity check.")

with st.sidebar:
    st.header("How to Use")
    st.write("- Upload clear scans/photos (PDF or images).")
    st.write("- Supports English/Hindi text.")
    st.write("- For bulk or institutional use, contact admin.")

uploaded_file = st.file_uploader("Choose a file", type=['pdf', 'jpg', 'jpeg', 'png'])

if uploaded_file is not None:
    if uploaded_file.type.startswith('image/'):
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Certificate", use_column_width=True)
    else:
        st.info("PDF uploaded, processing first page for preview...")

    if not wait_for_api():
        st.error("Verification API is starting up... please wait and refresh in a few seconds.")
    else:
        with st.spinner("Verifying... This may take up to 30 seconds."):
            files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            try:
                response = requests.post("http://127.0.0.1:8000/verify", files=files, timeout=60)
                if response.status_code == 200:
                    result = response.json()

                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("📊 Verification Report")
                        status_color = "🟢" if result["status"] == "Valid" else ("🟡" if result["status"] == "Caution" else "🔴")
                        st.markdown(f"**Status:** {status_color} {result['status']} ({result['confidence_score']}% Confidence)")
                        st.write("**Recommendation:**", result['recommendation'])

                        if result['anomalies']:
                            st.error("⚠️ Anomalies Detected:")
                            for anomaly in result['anomalies']:
                                st.write(f"- {anomaly}")
                        else:
                            st.success("✅ No issues found.")

                    with col2:
                        st.subheader("📄 Extracted Data")
                        for key, value in result['extracted_data'].items():
                            if value:
                                st.write(f"**{key.replace('_', ' ').title()}:** {value}")

                        st.write(f"**Document Hash:** {result['document_hash'][:16]}...")

                    report_json = json.dumps(result, indent=2, ensure_ascii=False)
                    st.download_button("📥 Download Report (JSON)", report_json, file_name="jacvs_report.json")
                else:
                    st.error(f"API Error: {response.text}")
            except Exception as e:
                st.error(f"Error: {str(e)}")

st.markdown("---")
st.markdown("Built for Jharkhand Education | Privacy: No data stored without consent.")
