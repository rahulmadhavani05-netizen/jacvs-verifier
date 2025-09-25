import pytesseract
from PIL import Image

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
