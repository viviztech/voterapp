import fitz  # PyMuPDF
import ollama
import io
from PIL import Image
import json
import re
import time
import os
import pytesseract
from database import run_query

# Configuration
PDF_PATH = '2026-EROLLGEN-S22-133-SIR-DraftRoll-Revision1-TAM-13-WI.pdf'
# DB_PATH is now handled by database.py
MODEL_NAME = 'llama3.2:3b'  # Text model for parsing Tesseract output

# Configure Ollama Host (Defaults to localhost, but can be set in Streamlit Secrets/Env)
OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
client = ollama.Client(host=OLLAMA_HOST)


def log_status(page_num, status, message=""):
    run_query(
        "INSERT INTO extraction_logs (page_number, status, error_message) VALUES (:p, :s, :e)",
        {"p": page_num, "s": status, "e": message}
    )

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

    response = client.chat(
        model=MODEL_NAME,
        messages=[{'role': 'user', 'content': prompt}],
        options={'temperature': 0} # Deterministic output
    )
    return response['message']['content']

def parse_and_store(page_num, raw_response, booth_id):
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
                # NOTE: SQLAlchemy uses :name for parameters
                run_query('''
                    INSERT INTO voters 
                    (epic_number, name, relation_type, relation_name, house_number, age, gender, polling_station_id, raw_text)
                    VALUES (:epic, :name, :rel_type, :rel_name, :house, :age, :gender, :booth, :raw)
                ''', {
                    "epic": v.get('epic_number'),
                    "name": v.get('name'),
                    "rel_type": v.get('relation_type'),
                    "rel_name": v.get('relation_name'),
                    "house": v.get('house_number'),
                    "age": int(v.get('age', 0)) if v.get('age') else 0,
                    "gender": v.get('gender'),
                    "booth": booth_id,
                    "raw": json.dumps(v)
                })
            except Exception as e:
                # print(f"Error inserting voter: {e}")
                pass
        
    except json.JSONDecodeError:
        print(f"Page {page_num}: Failed to parse JSON.")
        # Save raw response for debugging
        with open(f"failed_page_{page_num}.txt", "w") as f:
            f.write(raw_response)
        log_status(page_num, "FAILED", f"JSON Error. Saved to failed_page_{page_num}.txt")
    except Exception as e:
        print(f"Page {page_num}: Error: {e}")
        log_status(page_num, "FAILED", str(e))

def process_document(file_path, progress_callback=None):
    """
    Processes a PDF or Image file using Tesseract + Ollama.
    """
    if not os.path.exists(file_path):
        yield f"Error: File {file_path} not found."
        return

    # Check if text model exists
    try:
        models_info = client.list()
        model_names = [m['name'] for m in models_info['models']]
        if MODEL_NAME not in model_names and f"{MODEL_NAME}:latest" not in model_names:
             yield f"⚠️ Model '{MODEL_NAME}' not found. Downloading..."
             client.pull(MODEL_NAME)
    except Exception as e:
        yield f"Warning: Could not verify models: {e}. Attempting to proceed..."
    
    # Initialize DB (Booth info)
    current_booth_id = 1 
    # Use generic SQL compatible with both SQLite and Postgres
    # Use INSERT INTO ... (columns) VALUES ... 
    # ON CONFLICT behavior is tricky across DBs (IGNORE vs DO NOTHING). 
    # For now, just try insert, ignore error if duplicate ID (though generic default is often 1)
    try:
        run_query("INSERT INTO polling_stations (booth_no, location_name) VALUES (:booth_no, :location_name)",
                  {"booth_no": 'Unknown', "location_name": 'Default'})
    except Exception as e:
        # print(f"Polling station insert failed (likely exists): {e}")
        pass # Likely already exists

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
