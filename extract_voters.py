import fitz  # PyMuPDF
import sqlite3
import ollama
import io
from PIL import Image
import json
import re
import time
import os
import pytesseract

# Configuration
PDF_PATH = '2026-EROLLGEN-S22-133-SIR-DraftRoll-Revision1-TAM-13-WI.pdf'
DB_PATH = 'voter_data.db'
MODEL_NAME = 'llama3.2:3b'  # Text model for parsing Tesseract output


def log_status(page_num, status, message=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO extraction_logs (page_number, status, error_message) VALUES (?, ?, ?)",
              (page_num, status, message))
    conn.commit()
    conn.close()

def extract_text_from_image(image_bytes):
    """
    1. Uses Tesseract to get raw text.
    2. Uses Ollama (Text Model) to parse text into JSON.
    """
    # Step 1: Optical Character Recognition (Tesseract)
    with Image.open(io.BytesIO(image_bytes)) as img:
        # Tesseract prefers high contrast, raw images. No need to downscale.
        raw_text = pytesseract.image_to_string(img)
    
    # Check if text is too short (empty page)
    if len(raw_text.strip()) < 50:
        return "{}"

    # Step 2: LLM Parsing
    prompt = f"""
    You are a data extraction assistant. 
    Below is raw text extracted from an electoral roll using OCR. 
    Identify the voter records and output a valid JSON.
    
    Format:
    {{
      "voters": [
        {{
          "epic_number": "...",
          "name": "...", 
          "relation_type": "Father/Mother/Husband",
          "relation_name": "...",
          "house_number": "...",
          "age": 0,
          "gender": "Male/Female"
        }}
      ]
    }}

    Rules:
    - Only output valid JSON.
    - If a field is missing, use null or empty string.
    - Ignore headers/footers.

    Raw Text:
    {raw_text[:4000]} 
    """ 
    # Truncate text to fit context window if needed, though 4k is usually safe for lazy loading

    response = ollama.chat(
        model=MODEL_NAME,
        messages=[{'role': 'user', 'content': prompt}],
        options={'temperature': 0} # Deterministic output
    )
    return response['message']['content']

def parse_and_store(page_num, raw_response, booth_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        # robust json extraction
        json_match = re.search(r'\{.*\}|\[.*\]', raw_response.replace('\n', ' '), re.DOTALL)
        if json_match:
            cleaned_json = json_match.group(0)
        else:
            cleaned_json = raw_response

        # fix potential trailing commas or formatting issues simply by loading
        data = json.loads(cleaned_json)
        
        # Normalize list vs dict
        if isinstance(data, list):
            voters = data
        else:
            voters = data.get('voters', [])
            
        print(f"Page {page_num}: Found {len(voters)} voters.")
        
        for v in voters:
            try:
                c.execute('''
                    INSERT OR IGNORE INTO voters 
                    (epic_number, name, relation_type, relation_name, house_number, age, gender, polling_station_id, raw_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    v.get('epic_number'),
                    v.get('name'),
                    v.get('relation_type'),
                    v.get('relation_name'),
                    v.get('house_number'),
                    int(v.get('age', 0)) if v.get('age') else 0,
                    v.get('gender'),
                    booth_id,
                    json.dumps(v)
                ))
            except Exception as e:
                # print(f"Error inserting voter: {e}")
                pass
        
        conn.commit()
        
    except json.JSONDecodeError:
        print(f"Page {page_num}: Failed to parse JSON.")
        # Save raw response for debugging
        with open(f"failed_page_{page_num}.txt", "w") as f:
            f.write(raw_response)
        log_status(page_num, "FAILED", f"JSON Error. Saved to failed_page_{page_num}.txt")
    except Exception as e:
        print(f"Page {page_num}: Error: {e}")
        log_status(page_num, "FAILED", str(e))
    finally:
        conn.close()

def process_document(file_path, progress_callback=None):
    """
    Processes a PDF or Image file using Tesseract + Ollama.
    """
    if not os.path.exists(file_path):
        yield f"Error: File {file_path} not found."
        return

    # Check if text model exists
    try:
        models_info = ollama.list()
        model_names = [m['name'] for m in models_info['models']]
        if MODEL_NAME not in model_names and f"{MODEL_NAME}:latest" not in model_names:
             yield f"⚠️ Model '{MODEL_NAME}' not found. Downloading..."
             ollama.pull(MODEL_NAME)
    except Exception as e:
        yield f"Warning: Could not verify models: {e}. Attempting to proceed..."
    
    # Initialize DB (Booth info)
    current_booth_id = 1 
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO polling_stations (id, booth_no, location_name) VALUES (1, 'Unknown', 'Default')")
    conn.commit()
    conn.close()

    # Detect File Type
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.pdf':
        doc = fitz.open(file_path)
        total_pages = len(doc)
        yield f"Processing PDF {file_path} with {total_pages} pages..."

        # Process pages (Starting from page 2 usually, skipping cover)
        for page_num in range(2, total_pages):
            msg = f"Processing Page {page_num + 1}/{total_pages}..."
            if progress_callback:
                progress_callback(page_num, total_pages, msg)
            yield msg
            
            try:
                page = doc.load_page(page_num)
                # High DPI for Tesseract
                pix = page.get_pixmap(dpi=300) 
                img_data = pix.tobytes("png")
                
                raw_result = extract_text_from_image(img_data)
                parse_and_store(page_num + 1, raw_result, current_booth_id)
                log_status(page_num + 1, "COMPLETED")
            except Exception as e:
                error_msg = f"Failed to process page {page_num + 1}: {e}"
                print(error_msg)
                log_status(page_num + 1, "FAILED", str(e))
                yield error_msg

    elif ext in ['.jpg', '.jpeg', '.png', '.webp']:
        yield f"Processing Image {file_path}..."
        if progress_callback:
            progress_callback(1, 1, "OCR & Parsing...")
        
        try:
            with open(file_path, "rb") as f:
                img_data = f.read()
            
            raw_result = extract_text_from_image(img_data)
            parse_and_store(1, raw_result, current_booth_id)
            log_status(1, "COMPLETED")
            yield "Image Processing Complete."
        except Exception as e:
            error_msg = f"Failed to process image: {e}"
            print(error_msg)
            log_status(1, "FAILED", str(e))
            yield error_msg
    
    else:
        yield f"Unsupported file extension: {ext}"

def main():
    # Use the global PDF_PATH variable
    for status in process_document(PDF_PATH):
        print(status)

if __name__ == "__main__":
    main()
