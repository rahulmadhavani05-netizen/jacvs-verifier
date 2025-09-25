import streamlit as st
import json
from PIL import Image
import io
import pytesseract
import hashlib
from pdf2image import convert_from_bytes

# ---------------- OCR FUNCTION ----------------
def process_certificate_ocr(image):
    """
    Extracts important fields like name, roll number, and certificate ID
    from the given certificate image using Tesseract OCR.
    """
    try:
        # Convert image to text using pytesseract
        text = pytesseract.image_to_string(image)

        # Example: Extract fields using keyword searches
        extracted_data = {
            "name": "",
            "roll_no": "",
            "cert_id": ""
        }

        # Process the text line by line
        lines = text.split("\n")
        for line in lines:
            line_clean = line.strip()

            if "Name" in line_clean:
                extracted_data["name"] = line_clean.split(":")[-1].strip()
            elif "Roll" in line_clean or "Roll No" in line_clean:
                extracted_data["roll_no"] = line_clean.split(":")[-1].strip()
            elif "Certificate ID" in line_clean or "Cert ID" in line_clean:
                extracted_data["cert_id"] = line_clean.split(":")[-1].strip()

        # Confidence score is mocked here
        return {
            "extracted_data": extracted_data,
            "ocr_confidence": 85,  # Mock confidence
            "full_text": text
        }

    except Exception as e:
        return {
            "extracted_data": {},
            "ocr_confidence": 0,
            "full_text": "",
            "error": str(e)
        }

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

# File upload
uploaded_file = st.file_uploader("Choose a file", type=['pdf', 'jpg', 'jpeg', 'png'])

if uploaded_file is not None:
    # If it's a PDF, convert to image
    if uploaded_file.type == "application/pdf":
        images = convert_from_bytes(uploaded_file.read())
        if len(images) > 0:
            image = images[0]
        else:
            st.error("No pages found in PDF.")
            st.stop()
    else:
        image = Image.open(uploaded_file)

    # Display uploaded image
    st.image(image, caption="Uploaded Certificate", use_column_width=True)

    # Process OCR
    with st.spinner("🔍 Processing certificate..."):
        ocr_result = process_certificate_ocr(image)

        # Generate SHA256 hash
        img_bytes = io.BytesIO()
        image.save(img_bytes, format='PNG')
        document_hash = hashlib.sha256(img_bytes.getvalue()).hexdigest()

        # Mock database for validation
        MOCK_DB = {
            'John Doe': {'roll_no': 'RU12345', 'cert_id': 'RU/UG/2023/001'},
        }

        extracted_data = ocr_result.get('extracted_data', {})
        name = extracted_data.get('name', '').strip()
        roll_no = extracted_data.get('roll_no', '').strip()
        cert_id = extracted_data.get('cert_id', '').strip()

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

        # Final result
        result = {
            "status": status,
            "confidence_score": confidence_score,
            "recommendation": recommendation,
            "anomalies": anomalies,
            "extracted_data": extracted_data,
            "document_hash": document_hash,
            "full_text": ocr_result.get('full_text', '')
        }

    # ---------------- DISPLAY RESULTS ----------------
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

# Footer
st.markdown("---")
st.markdown("Built for **Jharkhand Education** | **Privacy Notice:** No data is stored without consent.")
