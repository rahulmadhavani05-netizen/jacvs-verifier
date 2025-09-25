# jacvs_ocr_enhanced.py
import pytesseract

def process_certificate_ocr(image):
    """
    Example OCR function that extracts text and mock data.
    Replace with your actual logic.
    """
    text = pytesseract.image_to_string(image)
    return {
        "full_text": text,
        "ocr_confidence": 85,
        "extracted_data": {
            "name": "John Doe",
            "roll_no": "RU12345",
            "cert_id": "RU/UG/2023/001"
        }
    }
