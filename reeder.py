import os
import json
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
from datetime import datetime
from google import genai
from google.genai import types

# Конфигурация GEMINI
GEMINI_API_KEY = "GEMINI_API_KEY"  
client = genai.Client(api_key=GEMINI_API_KEY)

# Подгон по оси Y
Y_OFFSET = 10    


def pdf_to_images(pdf_path, dpi=300):
    images = convert_from_path(pdf_path, dpi=dpi)
    return images

def perform_ocr(image):
    text = pytesseract.image_to_string(image)
    return text

def get_fill_coordinates(image):
    """
    Uses the Gemini API to determine coordinates for the signature, name, and date fields.
    Returns a JSON object with the coordinates or None in case of error.
    """
    prompt = (
        "You are a high-precision PDF document image analysis algorithm. "
        "Your task is to identify the presence and coordinates of fillable fields within the provided PDF page image.\n"
        "1. Fields to Detect:\n"
        "   - Signature field: An area designated for placing a signature image.\n"
        "   - Name field: An area designated for entering a person's name. Look for empty areas or fields located near labels such as 'Name', 'Full Name', or 'Surname'.\n"
        "   - Date field: An area designated for entering the date.\n"
        "2. Response Format:\n"
        "   - Return the result in strictly valid JSON format.\n"
        "   - For each detected field, provide its coordinates in the format: {'page': page_number, 'x': x_coordinate, 'y': y_coordinate, 'width': width, 'height': height}.\n"
        "   - Coordinates must be specified in points relative to the top-left corner of the PDF page.\n"
        "   - If a field is not detected, set its value to 'null'.\n"
        "   - Only return a JSON object, with no text before or after the JSON.\n"
        "3. JSON Response Structure:\n"
        "{\n"
        "  \"signature\": {...},\n"
        "  \"name\": {...},\n"
        "  \"date\": {...}\n"
        "}\n"
        "Example Response:\n"
        "{\n"
        "  \"signature\": {\"page\": 1, \"x\": 100, \"y\": 500, \"width\": 200, \"height\": 50},\n"
        "  \"name\": {\"page\": 1, \"x\": 100, \"y\": 400, \"width\": 250, \"height\": 30},\n"
        "  \"date\": {\"page\": 1, \"x\": 500, \"y\": 400, \"width\": 100, \"height\": 25}\n"
        "}\n"
        "Provide only the JSON response, without any additional explanations."
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, image]
        )
        print("API Response:", response)
    except Exception as e:
        print("Error calling Gemini API:", e)
        return None

    try:
        result_text = response.text.strip()
        json_start = result_text.find("```json")
        if json_start != -1:
            json_start += len("```json")
            json_end = result_text.find("```", json_start)
            if json_end != -1:
                result_text = result_text[json_start:json_end].strip()
        coordinates = json.loads(result_text)
        return coordinates
    except Exception as e:
        print("Error processing Gemini API response:", e)
        print("Response content:", response)
        return None

def apply_fields(pdf_path, signature_img_path, fields, name_text, date_text, output_pdf_path):
    doc = fitz.open(pdf_path)

    # ПОДПИСЬ
    if fields.get("signature"):
        sig = fields["signature"]
        page_number = sig.get("page", 1) - 1 
        x = sig.get("x", 0)
        y = max(sig.get("y", 0) - Y_OFFSET, 0)
        width = sig.get("width", 100)
        height = sig.get("height", 50)
        sig_rect = fitz.Rect(x, y, x + width, y + height)
        if page_number < len(doc):
            page = doc[page_number]
            page.insert_image(sig_rect, filename=signature_img_path)

    # ФИО
    if fields.get("name"):
        name_field = fields["name"]
        page_number = name_field.get("page", 1) - 1
        x = name_field.get("x", 0)
        y = max(name_field.get("y", 0) - Y_OFFSET, 0)
        width = name_field.get("width", 100)
        height = name_field.get("height", 20)
        rect = fitz.Rect(x, y, x + width, y + height)
        if page_number < len(doc):
            page = doc[page_number]
            page.insert_textbox(rect, name_text, fontsize=12, color=(0, 0, 0))

    # ДАТА
    if fields.get("date"):
        date_field = fields["date"]
        page_number = date_field.get("page", 1) - 1
        x = date_field.get("x", 0)
        y = max(date_field.get("y", 0) - Y_OFFSET, 0)
        width = date_field.get("width", 100)
        height = date_field.get("height", 20)
        rect = fitz.Rect(x, y, x + width, y + height)
        if page_number < len(doc):
            page = doc[page_number]
            page.insert_textbox(rect, date_text, fontsize=12, color=(0, 0, 0))

    doc.save(output_pdf_path)
    doc.close()
    print("✅ Filled and signed PDF saved as:", output_pdf_path)

def sign_pdf(pdf_path, signature_img_path, name_text, output_pdf_path):
    images = pdf_to_images(pdf_path)
    if not images:
        print("Failed to convert PDF to images.")
        return

    first_page_image = images[0]
    date_text = datetime.now().strftime("%Y-%m-%d")

    fields = get_fill_coordinates(first_page_image)
    if not fields:
        print("Failed to obtain field coordinates from the Gemini API.")
        return

    print("Field coordinates obtained:", fields)
    apply_fields(pdf_path, signature_img_path, fields, name_text, date_text, output_pdf_path)

if __name__ == "__main__":
    name_text = input("Enter your full name: ").strip()
