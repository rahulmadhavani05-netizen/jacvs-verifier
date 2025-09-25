import streamlit as st
import json
from PIL import Image
import io
import threading
import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
import pytesseract
from jacvs_ocr_enhanced import process_certificate_ocr  # Import your OCR function
import hashlib
import os
import requests

# ✅ Ensure python-multipart is available
try:
    import multipart
except ImportError:
    st.error("Missing dependency: Install it using `pip install python-multipart`")
    st.stop()

# ---------------- FASTAPI BACKEND ----------------
app = FastAPI(title="JACVS API")

@app.post("/verify")
async def verify_certificate(file: UploadFile = File(...)):
    try:
        # Read file content
        contents = await file.read()

        # Process Image or PDF
        if file.content_type.startswith('image/'):
            image = Image.open(io.BytesIO(contents))
        elif file.content_type == 'application/pdf':
            from pdf2image import convert_from_bytes
            images = convert_from_bytes(contents)
            image = images[0] if images else None
        else:
            return JSONResponse(status_code=400, content={"error": "Unsupported file type"})

        if not image:
            return JSONResponse(status_code=400, content={"error": "No image extracted"})

        # Run OCR
        ocr_result = process_certificate_ocr(image)

        # Generate SHA256 hash for the uploaded file
        img_bytes = io.BytesIO()
        image.save(img_bytes, format='PNG')
        document_hash = hashlib.sha256(img_bytes.getvalue()).hexdigest()

        # Extract data from OCR result
        extracted_data = ocr_result.get('extracted_data', {})
        name = extracted_data.get('name', '').strip()
        roll_no = extracted_data.get('roll_no', '').strip()
        cert_id = extracted_data.get('cert_id', '').strip()

        # Mock database for validation
        MOCK_DB = {
            'John Doe': {'roll_no': 'RU12345', 'cert_id': 'RU/UG/2023/001'},
            # Add more sample records for testing
        }

        anomalies = []
        confidence_score = 85
        status = "Valid"
        recommendation = "Proceed with verification."

        # Verification logic
        if name in MOCK_DB:
            if MOCK_DB[name]['roll_no'] != roll_no or MOCK_DB[name]['cert_id'] != cert_id:
                anomalies.append("Mismatch in Roll No or Certificate ID")
                status = "Caution"
                confidence_score = 60
                recommendation = "Manual review recommended."
        else:
            anomalies.append("Name not found in records")
            status = "Forged"
            confidence_score = 30
            recommendation = "Document appears invalid."

        if ocr_result.get('ocr_confidence', 0) < 70:
            anomalies.append("Low OCR confidence - blurry image?")

        # Final response
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


# ---------------- FASTAPI SERVER THREAD ----------------
def run_api():
    """Runs the FastAPI backend server in a background thread."""
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)
    server.run()

# Start the FastAPI server in a background thread (only once)
if 'api_thread' not in st.session_state:
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    st.session_state.api_thread = api_thread
    st.rerun()  # Refresh to ensure API thread is ready


# ---------------- STREAMLIT FRONTEND ----------------
st.set_page_config(page_title="JACVS Verifier", layout="wide")

st.title("🛡️ JACVS - Jharkhand Academic Credential Verification System")
st.markdown("Upload a certificate (PDF/JPG/PNG) for instant authenticity check.")

# Sidebar Instructions
with st.sidebar:
    st.header("How to Use")
    st.write("- Ensure the certificate is scanned clearly.")
    st.write("- Supported formats: PDF, JPG, JPEG, PNG")
    st.write("- For institutions: Contact admin for bulk verification tools.")

uploaded_file = st.file_uploader("Choose a file", type=['pdf', 'jpg', 'jpeg', 'png'])

if uploaded_file is not None:
    # Display uploaded image preview
    if uploaded_file.type.startswith('image/'):
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Certificate", use_column_width=True)

    # Call the backend API for verification
    with st.spinner("Verifying... Please wait 10-30 seconds."):
        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        try:
            response = requests.post("http://127.0.0.1:8000/verify", files=files, timeout=60)

            if response.status_code == 200:
                result = response.json()

                # Display results in two columns
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

                    st.write(f"**Document Hash:** {result['document_hash'][:16]}...")  # Show only first 16 chars

                # Download JSON report
                report_json = json.dumps(result, indent=2, ensure_ascii=False)
                st.download_button(
                    "📥 Download Report (JSON)",
                    report_json,
                    file_name="jacvs_report.json",
                    mime="application/json"
                )

            else:
                st.error(f"API Error ({response.status_code}): {response.text}")

        except requests.exceptions.ConnectionError:
            st.error("⚡ API is starting up... Please refresh after 10 seconds.")
        except Exception as e:
            st.error(f"Unexpected Error: {str(e)}")

# Footer
st.markdown("---")
st.markdown("Built for **Jharkhand Education** | **Privacy Notice:** No data is stored without consent.")
