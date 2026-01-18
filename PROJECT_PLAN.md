# Project Plan: Voter List OCR & Analysis

## 1. Project Overview
**Objective**: Extract voter information (Assembly Booth wise) from the PDF `2026-EROLLGEN-S22-133-SIR-DraftRoll-Revision1-TAM-13-WI.pdf` using the local AI OCR tool (`local_ai_ocr` / DeepSeek-OCR).
**Goal**: converting unstructured PDF data into a structured Database for analysis.

## 2. Technical Architecture
- **Input**: PDF Documents (Electoral Rolls).
- **Core Engine**: Python.
- **OCR Engine**: Ollama running `deepseek-ocr:3b` (via `local_ai_ocr` logic).
- **Preprocessing**: `PyMuPDF` (fitz) to convert PDF pages to high-res images.
- **Data Parsing**: Custom parsing logic to map OCR text to structured fields.
- **Storage**: SQLite Database (lightweight, file-based, easy to analyze).

## 3. Database Structure

We will use a Relational Database (SQLite) with two main tables: `polling_stations` and `voters`.

### Table 1: polling_stations
Stores information about the assembly booths/sections.

```sql
CREATE TABLE polling_stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booth_no VARCHAR(50),
    part_no VARCHAR(50), -- Part Number (e.g., 13)
    section_no VARCHAR(50),
    location_name TEXT,
    assembly_constituency TEXT,
    UNIQUE(part_no, section_no)
);
```

### Table 2: voters
Stores individual voter details extracted from the list.

```sql
CREATE TABLE voters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    epic_number VARCHAR(20) UNIQUE, -- The ID Card Number (e.g., S22...)
    name TEXT,
    relation_type VARCHAR(10), -- 'Father', 'Husband', 'Mother', 'Other'
    relation_name TEXT,
    house_number TEXT,
    age INTEGER,
    gender VARCHAR(10),
    polling_station_id INTEGER,
    raw_text TEXT, -- For debugging verification
    FOREIGN KEY (polling_station_id) REFERENCES polling_stations(id)
);
```

### Table 3: extraction_logs
To track progress and errors.

```sql
CREATE TABLE extraction_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_number INTEGER,
    status VARCHAR(20), -- 'PENDING', 'COMPLETED', 'FAILED'
    error_message TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 4. Implementation Steps

### Step 1: Environment Setup
1.  Install **Ollama** (if not already installed) on the Mac.
2.  Pull the required model:
    ```bash
    ollama pull deepseek-ocr:3b
    ```
    *(Note: If `deepseek-ocr:3b` is custom/private, we may need to build it from the `local_ai_ocr` Modelfile or use a substitute like `llama3.2-vision`)*.
3.  Install Python dependencies:
    ```bash
    pip install ollama PyMuPDF pillow
    ```

### Step 2: Develop Extraction Pipeline (`extract.py`)
This script will:
1.  Connect to `voter_data.db`.
2.  Open the PDF using `fitz`.
3.  Iterate through each page.
4.  **Detect Header**: If page contains "Assembly Constituency", parse the Booth/Part info and update `current_polling_station_id`.
5.  **Detect Voter Records**:
    - Convert page to image.
    - Send image to Ollama with a prompt: *"Extract all voter entries from this image. Return structured JSON with fields: EPIC, Name, Relation, Age, Gender, HouseNo."*
    - **Optimization**: Crop the image into segments (e.g., 10 voters per block) to improved OCR accuracy if full-page OCR fails.
6.  Cleaner/Validator: Ensure "Age" is numeric, "Gender" is standard, etc.
7.  Insert valid records into `voters` table.

### Step 3: Analysis Script
Identify insights such as:
- **Gen Z Voters (18-29)**: Count/Percentage and gender distribution.
- Total voters per booth.
- Gender ratio.
- Family groupings (by House Number).

## 5. Execution Plan
1.  **Setup**: Run setup commands today.
2.  **Prototype**: Test extraction on **Page 3** (usually the first voter list page) to tune the prompt.
3.  **Batch Run**: Run the script for the full PDF (can take 1-2 hours depending on GPU).
4.  **QA**: Manually verify 5-10 random entries against the PDF.
