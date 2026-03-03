# QDArchive – Qualitative Data Acquisition Pipeline  
FAU Erlangen – Seeding QDArchive Project (Winter 2025/26)

## Overview

This repository contains the implementation of **Part 1 – Data Acquisition** for the QDArchive seminar/project.

The goal is to systematically collect **openly licensed qualitative research data** and, where available, **QDA (Qualitative Data Analysis) project files** from public repositories such as Zenodo, Figshare, Dataverse, GitHub, and others.

The pipeline:

1. Queries public repositories via APIs
2. Validates open licenses
3. Detects QDA-specific file formats
4. Downloads files
5. Extracts and stores structured metadata
6. Exports metadata as CSV
7. Creates a local qualitative data archive

This repository focuses on reproducibility, structured metadata management, and license compliance.

---

## Project Scope

This project contributes to the seeding of QDArchive, a web service for publishing and archiving qualitative research data.

Data types targeted:

- Interview transcripts
- Focus group transcripts
- Ethnographic field notes
- Oral history collections
- Coded qualitative datasets
- QDA project exports (.qdpx, .nvpx, .atlproj, etc.)

Only datasets with explicit open licenses (e.g., Creative Commons) are included.

---

## Repository Structure
.
├── src/ # Pipeline source code
├── data/
│ ├── raw/ # Downloaded datasets
│ └── db.sqlite # Metadata database
├── exports/
│ └── metadata.csv # Exported metadata
├── logs/ # Optional logging output
├── requirements.txt
└── README.md



---

## Architecture

The acquisition pipeline is structured into modular components:

### 1. Source Connectors
Each supported repository has a connector module:
- Zenodo API
- Figshare API
- Dataverse API
- GitHub API (for QDA formats)

Each connector implements:
- `search(query)`
- `get_record(record_id)`

### 2. Validation Layer
For each dataset:
- License verification
- Open-access check
- File list inspection
- QDA file detection
- Qualitative content flagging

### 3. Storage Layer
- Files stored in structured directories:

data/raw/<source>/<record_id>/

- Metadata stored in SQLite
- Exportable to CSV

---

## Supported QDA Formats

The pipeline detects the following formats:

- `.qdpx` (REFI-QDA exchange format)
- `.nvpx`, `.nvp` (NVivo)
- `.atlproj` (ATLAS.ti)
- `.mx`, `.mx22` (MAXQDA)
- `.zip` (inspected for embedded QDA formats)

Datasets are tagged with:

- `has_qda_export` (boolean)
- `has_qual_data` (boolean)

---

## Metadata Schema (Core Fields)

| Field | Description |
|-------|-------------|
| source | Repository name |
| source_record_id | Unique identifier in source |
| title | Dataset title |
| creators | Authors |
| publication_date | Publication date |
| license | License information |
| landing_page_url | Dataset landing page |
| file_name | Name of downloaded file |
| file_extension | Detected extension |
| has_qda_export | QDA project file detected |
| has_qual_data | Qualitative data detected |
| notes | Manual observations |

The schema may evolve during the project.

---

## Installation

```bash
git clone https://github.com/<your-username>/qdarchive-acquisition.git
cd qdarchive-acquisition
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt