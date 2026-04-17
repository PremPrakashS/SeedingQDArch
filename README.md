# SeedingQDArch

A comprehensive data acquisition pipeline for harvesting qualitative data analysis (QDA) datasets from multiple international repositories. This project automates the discovery, filtering, and download of research datasets containing QDA software projects, qualitative research methodologies, and associated documentation.

## Project Overview

SeedingQDArch is built to:
- Query multiple open research repositories (Zenodo, Dryad, Figshare, CESSDA)
- Search for datasets related to qualitative data analysis using domain-specific keywords
- Filter results by open licenses (CC-BY, CC0, ODC-BY, PDDL, etc.)
- Extract structured metadata (titles, authors, DOIs, keywords, file listings)
- Download complete datasets and individual files to local storage
- Maintain a SQLite database for tracking collection progress and download status
- Support incremental collection and resumable downloads

## Repository Sources

The pipeline queries data from four major repositories:

| Repository | API | Type | License Parsing | Notes |
|-----------|-----|------|-----------------|-------|
| **Zenodo** | https://zenodo.org/api/records | File repository | Native CC licenses | Default, supports all filters |
| **Dryad** | https://datadryad.org/api/v2 | Data repository | Native licenses | Complements Zenodo, high-quality datasets |
| **Figshare** | https://api.figshare.com/v2 | Institutional repository | License parsing | Large collection, research articles |
| **CESSDA** | https://datacatalogue.cessda.eu/api | Metadata catalog | Default to CC-BY for open | European social science data |

### Search Keywords

The pipeline uses three-tier search strategies:

1. **QDA Software** — High-precision queries for specific tools:
   - File extensions: `qdpx`, `nvpx`, `atlproj`, `mx22`, `hpr`, `f4p`
   - Software names: NVivo, ATLAS.ti, MaxQDA, Dedoose, QDAcity, Transana, f4analyse
   - Standards: `REFI-QDA`, `CAQDAS`

2. **Qualitative Methodology** — Broader English-language queries:
   - Research approaches: ethnography, grounded theory, case study research, action research
   - Data types: interview transcripts, focus groups, coded transcripts
   - Analysis methods: thematic analysis, narrative analysis, phenomenological research

3. **Multilingual** — International queries in German, Dutch, Norwegian, Spanish, French, Portuguese

Open licenses accepted:
- `cc-by` (Creative Commons Attribution)
- `cc0` / `cc-zero` (Creative Commons Zero)
- `odc-by` (Open Data Commons Attribution)
- `pddl` (Public Domain Dedication and License)
- `cc-pddc` (Creative Commons Public Domain Dedication)

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Setup

1. **Clone or download the repository:**
   ```bash
   cd /path/to/SeedingQDArch
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   Dependencies:
   - `requests>=2.31.0` — HTTP library for API calls
   - `pandas>=2.0.0` — Data manipulation and CSV export
   - `certifi>=2024.0.0` — SSL certificate verification

3. **Verify installation:**
   ```bash
   python collect_data.py --help
   python download_data.py --help
   ```

## Quick Start

### 1. Collect Data from All Repositories

```bash
# Default: Zenodo & Dryad only
python collect_data.py --collect

# Include Figshare
python collect_data.py --collect --figshare

# Include CESSDA
python collect_data.py --collect --cessda

# Include everything (recommended for comprehensive collection)
python collect_data.py --collect --figshare --cessda
```

**Time estimate:** 15-30 minutes for 38 queries across all sources

**Output:**
- SQLite database: `database/23100834-seeding.db`
- CSV exports: `exports/projects.csv`, `exports/files.csv`
- Statistics displayed at completion

### 2. Check What's Been Collected

```bash
python download_data.py --stats
```

**Example output:**
```
Total projects:  953
Total files:     2,847

Files by status:
  pending    2,847  (100.0%)
  success       0  (  0.0%)
  failed        0  (  0.0%)
  skipped       0  (  0.0%)
```

### 3. Download All Files

```bash
# Download with resume capability
python download_data.py --download-all --resume

# Download to custom directory
python download_data.py --download-all --output-dir my_datasets

# Download with size limits (skip files > 1GB)
python download_data.py --download-all --max-file-size-mb 1000
```

### 4. Download Specific File Types

```bash
# Download only ZIP archives (complete datasets)
python download_data.py --download-zip

# Download by extension
python download_data.py --download-by-type pdf
python download_data.py --download-by-type xlsx
python download_data.py --download-by-type docx
```

## Complete Workflows

### Workflow 1: Fresh Start (Full Collection + Download)

```bash
# Step 1: Reset and collect from all sources
python collect_data.py --reset --collect --figshare --cessda --export

# Step 2: Review statistics
python download_data.py --stats

# Step 3: Download all files
python download_data.py --download-all --resume

# Step 4: Check for failures
python download_data.py --failed

# Step 5: Retry failed downloads
python download_data.py --retry-failed
```

### Workflow 2: Incremental Collection (Add Repositories Over Time)

```bash
# Run 1: Initial collection from Zenodo & Dryad
python collect_data.py --collect

# Run 2: Later, add Figshare
python collect_data.py --collect --figshare

# Run 3: Later, add CESSDA
python collect_data.py --collect --cessda

# Finally: Download everything (new and existing data)
python download_data.py --download-all --resume
```

### Workflow 3: Large-Scale Collection with Advanced Options

```bash
# Collect with all options and custom pagination
python collect_data.py --reset \
  --collect --figshare --cessda --multilingual \
  --max-pages 10 --page-size 50 \
  --export

# Download in stages
python download_data.py --download-zip          # Archives first
python download_data.py --download-all --resume # Everything else
```

## Command Reference

### `collect_data.py` — Data Collection

Extract and populate the database from repositories.

#### Basic Usage
```bash
python collect_data.py [OPTIONS]
```

#### Collection Options
| Option | Description | Default |
|--------|-------------|---------|
| `--collect` | Run collection queries | - |
| `--reset` | Reset database (destructive, deletes all data) | - |
| `--export` | Export metadata to CSV | - |
| `--figshare` | Include Figshare | Excluded |
| `--cessda` | Include CESSDA | Excluded |
| `--multilingual` | Include multilingual queries | English only |
| `--max-pages N` | Max pages per query | 3 |
| `--page-size N` | Results per page | 25 |

#### Examples
```bash
# Collect from Zenodo & Dryad with export
python collect_data.py --collect --export

# Include Figshare with 5 pages per query
python collect_data.py --collect --figshare --max-pages 5

# Full international collection
python collect_data.py --collect --figshare --cessda --multilingual

# Fresh start with everything
python collect_data.py --reset --collect --figshare --cessda --export
```

### `download_data.py` — File Downloads

Download files from datasets already in the database.

#### Basic Usage
```bash
python download_data.py [OPTIONS]
```

#### Download Actions
| Option | Description |
|--------|-------------|
| `--download-all` | Download all pending files |
| `--download-zip` | Download only ZIP files |
| `--download-by-type EXT` | Download specific type (pdf, xlsx, docx, etc.) |
| `--download-by-status ST` | Download by status (pending, success, failed, skipped) |
| `--retry-failed` | Retry previously failed downloads |

#### View Actions
| Option | Description |
|--------|-------------|
| `--stats` | Show statistics and exit |
| `--pending` | List pending files (up to 50) |
| `--failed` | List failed files |

#### Download Options
| Option | Description | Default |
|--------|-------------|---------|
| `--resume` | Resume downloads (skip already attempted) | - |
| `--output-dir DIR` | Custom output directory | `downloads/` |
| `--max-file-size-mb MB` | Skip files larger than this | 500 |
| `--timeout SEC` | Request timeout | 120 |
| `--delay SEC` | Delay between requests | 1.0 |

#### Examples
```bash
# Download all with resume capability
python download_data.py --download-all --resume

# Download to custom location with size limit
python download_data.py --download-all --output-dir datasets --max-file-size-mb 2000

# Download PDFs only
python download_data.py --download-by-type pdf

# Check status before downloading
python download_data.py --stats
python download_data.py --pending

# Retry failed downloads with longer timeout
python download_data.py --retry-failed --timeout 300
```

## Project Structure

```
SeedingQDArch/
├── clients/                      # Repository API clients
│   ├── base_client.py           # Abstract base class with retry logic
│   ├── zenodo_client.py         # Zenodo API (default)
│   ├── dryad_client.py          # Dryad API
│   ├── figshare_client.py       # Figshare API (POST-based)
│   └── cessda_client.py         # CESSDA catalog API (scraping)
│
├── models/                       # Data models
│   └── record.py                # DatasetRecord and FileRecord dataclasses
│
├── params/                       # Configuration
│   └── config.py                # Search queries, API endpoints, licenses
│
├── pipeline/                     # Data processing
│   ├── collector.py             # Query orchestration and database population
│   ├── database.py              # SQLite database management
│   ├── downloader.py            # File download logic with status tracking
│   └── filter.py                # Dataset filtering by license and relevance
│
├── collect_data.py              # CLI: Data collection script
├── download_data.py             # CLI: File download script
├── run_pipeline.py              # CLI: Full pipeline (reference implementation)
│
├── database/                     # SQLite database (created at runtime)
│   └── 23100834-seeding.db      # Main project database
│
├── downloads/                    # Downloaded files (created at runtime)
│
├── exports/                      # CSV exports (created at runtime)
│   ├── projects.csv
│   └── files.csv
│
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## Database Schema

The SQLite database contains the following main tables:

| Table | Purpose |
|-------|---------|
| `projects` | Dataset metadata (title, DOI, authors, license, source) |
| `files` | File listings with download URLs and status |
| `keywords` | Tags/keywords per dataset |
| `person_role` | Authors/creators per dataset |
| `licenses` | License information |
| `relevance_scores` | Quality/relevance scores for filtering |

**Note:** Data is preserved when creating database instances or running scripts multiple times. Use `--reset` flag only when explicitly resetting all data.

## Download File Status

Each downloaded file is tracked with one of these statuses:

| Status | Meaning |
|--------|---------|
| `pending` | Not yet attempted |
| `success` | Successfully downloaded |
| `failed` | Download attempt failed |
| `skipped` | Skipped due to filter (e.g., file size limit) |

Check status with: `python download_data.py --stats`

## Troubleshooting

### "No database found"
```bash
# Initialize database and start collection
python collect_data.py --collect --export
```

### "No files to download"
```bash
# Verify collection succeeded
python download_data.py --stats

# If file count is 0, collection may have failed
python collect_data.py --collect
```

### "Rate limit errors" during collection
```bash
# Reduce query frequency
python collect_data.py --collect --max-pages 1 --page-size 25
```

### "Download keeps failing"
```bash
# Check what failed
python download_data.py --failed

# Retry with longer timeout
python download_data.py --retry-failed --timeout 300

# Or retry with delay
python download_data.py --retry-failed --delay 2.0
```

### "Downloads interrupted/incomplete"
```bash
# Resume downloads from where they stopped
python download_data.py --download-all --resume
# Already-downloaded files are skipped automatically
```

### "Want to start over"
```bash
# Backup current database (optional)
cp database/23100834-seeding.db database/23100834-seeding.db.backup

# Reset and start fresh
python collect_data.py --reset --collect --figshare --cessda --export
```

## Performance Tips

### For Slow Networks
```bash
# Use longer timeouts and add request delays
python download_data.py --download-all \
  --timeout 300 \
  --delay 2.0 \
  --max-file-size-mb 200
```

### For Comprehensive Collection
```bash
# Increase pages per query (slower but more results)
python collect_data.py --collect --max-pages 10 --page-size 50
```

### For Limited Storage
```bash
# Download only archive files (ZIP) or specific types
python download_data.py --download-zip

# Or skip large files
python download_data.py --download-all --max-file-size-mb 200
```

## Data Safety

**Important:** The database now safely preserves data across multiple runs. Creating database instances or running scripts multiple times will NOT delete data.

- ✅ **Safe:** Running collection multiple times (appends new data, preserves existing)
- ✅ **Safe:** Running download script multiple times (updates status, preserves files)
- ⚠️ **Destructive:** Using `--reset` flag (explicitly deletes ALL data)

Only use `--reset` when you intentionally want to start fresh.

## Export Data

Export collected metadata to CSV:

```bash
# Export during collection
python collect_data.py --collect --export

# Or export existing data without collection
python collect_data.py --export
```

**Output files:**
- `exports/projects.csv` — Dataset metadata (one row per dataset)
- `exports/files.csv` — File listings (one row per file)

## Available Commands Summary

| Task | Command |
|------|---------|
| Collect from default sources | `python collect_data.py --collect` |
| Collect from all sources | `python collect_data.py --collect --figshare --cessda` |
| Check download statistics | `python download_data.py --stats` |
| Download all files | `python download_data.py --download-all` |
| Resume interrupted downloads | `python download_data.py --download-all --resume` |
| Download only ZIP files | `python download_data.py --download-zip` |
| Download by file type | `python download_data.py --download-by-type pdf` |
| See pending downloads | `python download_data.py --pending` |
| See failed downloads | `python download_data.py --failed` |
| Retry failed downloads | `python download_data.py --retry-failed` |
| Export metadata to CSV | `python collect_data.py --export` |
| Reset database | `python collect_data.py --reset --collect` |

## API Endpoints Reference

| Source | Endpoint | Type |
|--------|----------|------|
| Zenodo | https://zenodo.org/api/records | GET (Lucene queries) |
| Dryad | https://datadryad.org/api/v2 | GET |
| Figshare | https://api.figshare.com/v2/articles/search | POST |
| CESSDA | https://datacatalogue.cessda.eu/api/DataSets/v2/search | GET (REST) |

## License

This project is designed to work with open-licensed datasets. All collected datasets must have open licenses (CC-BY, CC0, ODC-BY, PDDL, CC-PDDC).

## Contact & Support

For issues, questions, or contributions:
- Check existing documentation in the project root
- Review command help: `python collect_data.py --help` or `python download_data.py --help`
- Consult troubleshooting section above

## Notes

- **Zenodo API Rate Limit:** Unauthenticated requests capped at 25 results/page. For higher limits, create a free Zenodo account and pass your token to ZenodoClient.
- **Download Resumption:** The `--resume` flag automatically skips already-downloaded files when continuing interrupted downloads.
- **File Size Management:** Use `--max-file-size-mb` to automatically skip large files and avoid storage/timeout issues.
- **Repository Behavior:** Each repository has unique pagination, license formats, and API patterns; the pipeline abstracts these differences.
- **Incremental Collection:** Safe to collect from different repositories at different times; data accumulates in the database.

---

**Last Updated:** 2026-04-17  
**Version:** 2.0 (Split pipeline with independent collection and download scripts)
