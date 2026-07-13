#!/usr/bin/env python3
"""
QDArchive Text Extraction Pipeline — Extract text from downloaded files.

Reads every file recorded in the database that is present on disk, extracts its
text (PDF, DOCX, XLSX, and any plain-text / markup format), writes it to a .txt
file under a separate output directory, and records the location in the
`extracted_texts` table. Binary/media/unsupported formats are skipped.

Usage:
    python extract_text.py                       # extract all (skip already done)
    python extract_text.py --output-dir extracted_text
    python extract_text.py --overwrite           # re-extract everything
    python extract_text.py --stats               # show extraction stats and exit
"""
import sys
import argparse
from datetime import datetime

from pipeline.database import QDArchDatabase
from pipeline.text_extractor import TextExtractor

# UTF-8 console so printing non-cp1252 filenames doesn't crash on Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def main():
    parser = argparse.ArgumentParser(
        description="QDArchive Text Extraction Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--source-dir", default="downloads",
                        help="Where downloaded files live (default: downloads)")
    parser.add_argument("--output-dir", default="extracted_text",
                        help="Where to write extracted .txt files (default: extracted_text)")
    parser.add_argument("--max-file-size-mb", type=float, default=200.0,
                        help="Skip files larger than this (default: 200)")
    parser.add_argument("--overwrite", action="store_true",
                        help="Re-extract files that already have a record")
    parser.add_argument("--stats", action="store_true",
                        help="Show extraction statistics and exit")

    args = parser.parse_args()

    db_path = "database/23100834-seeding.db"
    db = QDArchDatabase(db_path=db_path)
    print(f"Database: {db_path}\n")

    if args.stats:
        print("=" * 70)
        print("TEXT EXTRACTION STATISTICS")
        print("=" * 70)
        total = db.query("SELECT COUNT(*) AS n FROM extracted_texts").iloc[0]["n"]
        print(f"Files with extracted text: {total}")
        if total:
            by_type = db.query(
                "SELECT file_type, COUNT(*) AS n, SUM(char_count) AS chars "
                "FROM extracted_texts GROUP BY file_type ORDER BY n DESC"
            )
            print("\nBy file type:")
            for _, r in by_type.iterrows():
                print(f"  {str(r['file_type']):8s}  {int(r['n']):5d} files  {int(r['chars'] or 0):>12,} chars")
        print()
        return

    print("=" * 70)
    print("TEXT EXTRACTION")
    print("=" * 70)
    print(f"Source directory: {args.source_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"Max file size:    {args.max_file_size_mb} MB")
    print(f"Overwrite:        {args.overwrite}\n")

    extractor = TextExtractor(
        db=db,
        source_root=args.source_dir,
        output_root=args.output_dir,
        max_file_size_mb=args.max_file_size_mb,
        overwrite=args.overwrite,
    )

    start = datetime.now()
    summary = extractor.extract_all()
    elapsed = datetime.now() - start

    print("\n" + "=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)
    print(f"  Extracted:        {summary['extracted']}")
    print(f"  Empty (no text):  {summary['empty']}")
    print(f"  Skipped (type):   {summary['skipped_type']}")
    print(f"  Missing on disk:  {summary['missing']}")
    print(f"  Failed:           {summary['failed']}")
    print(f"  Already done:     {summary['already']}")
    print(f"\nElapsed: {elapsed}\n")


if __name__ == "__main__":
    main()
