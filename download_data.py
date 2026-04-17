#!/usr/bin/env python3
"""
QDArchive Data Download Pipeline — Download Files from Database

This script downloads files from datasets already collected in the database.
It reads metadata from the database and streams files to local storage.

Usage:
    python download_data.py --help
    python download_data.py --download-all          # Download all pending files
    python download_data.py --download-zip          # Download only ZIP files
    python download_data.py --download-by-status pending
    python download_data.py --download-all --resume  # Resume interrupted downloads
    python download_data.py --stats                 # Show download statistics
    python download_data.py --retry-failed          # Retry previously failed files
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

from pipeline.database import QDArchDatabase
from pipeline.downloader import DatasetDownloader


def main():
    parser = argparse.ArgumentParser(
        description="QDArchive Data Download Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Download actions
    download_group = parser.add_mutually_exclusive_group()
    download_group.add_argument(
        "--download-all",
        action="store_true",
        help="Download all pending files",
    )
    download_group.add_argument(
        "--download-zip",
        action="store_true",
        help="Download only ZIP files (full dataset archives)",
    )
    download_group.add_argument(
        "--download-by-type",
        type=str,
        help="Download files by extension (e.g., 'pdf', 'xlsx', 'docx')",
    )
    download_group.add_argument(
        "--download-by-status",
        type=str,
        default="pending",
        help="Download files by status (pending, success, failed, skipped)",
    )
    download_group.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry previously failed downloads",
    )

    # View actions
    view_group = parser.add_mutually_exclusive_group()
    view_group.add_argument(
        "--stats",
        action="store_true",
        help="Show download statistics and exit",
    )
    view_group.add_argument(
        "--pending",
        action="store_true",
        help="List pending downloads and exit",
    )
    view_group.add_argument(
        "--failed",
        action="store_true",
        help="List failed downloads and exit",
    )

    # Download options
    parser.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="Resume downloads (skip already attempted)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="downloads",
        help="Output directory for downloads (default: downloads)",
    )
    parser.add_argument(
        "--max-file-size-mb",
        type=float,
        default=500.0,
        help="Skip files larger than this (MB, default: 500)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Request timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="Delay between requests in seconds (default: 1.0)",
    )

    args = parser.parse_args()

    # Show help if no arguments
    if not any([
        args.download_all,
        args.download_zip,
        args.download_by_type,
        args.download_by_status,
        args.retry_failed,
        args.stats,
        args.pending,
        args.failed,
    ]):
        parser.print_help()
        return

    # Initialize database
    db_path = "database/23100834-seeding.db"
    db = QDArchDatabase(db_path=db_path)
    print(f"Database: {db_path}\n")

    # Show statistics
    if args.stats:
        print("=" * 70)
        print("DOWNLOAD STATISTICS")
        print("=" * 70)
        stats = db.get_stats()
        print(f"Total projects:  {stats['total_projects']}")
        print(f"Total files:     {stats['total_files']}\n")

        print("Files by status:")
        total = stats['total_files']
        for status, count in stats['files_by_status'].items():
            pct = 100 * count / total if total > 0 else 0
            print(f"  {status:10s}  {count:4d}  ({pct:5.1f}%)")
        print()
        return

    # Show pending downloads
    if args.pending:
        print("=" * 70)
        print("PENDING DOWNLOADS")
        print("=" * 70)
        files = db.query(
            "SELECT id, file_name, file_type, download_url FROM files WHERE status = 'pending' LIMIT 50"
        )
        if len(files) > 0:
            print(f"Showing first 50 of {len(files)} pending files:\n")
            for _, row in files.iterrows():
                print(f"  {row['file_name']:50s} ({row['file_type']})")
        else:
            print("No pending downloads.")
        print()
        return

    # Show failed downloads
    if args.failed:
        print("=" * 70)
        print("FAILED DOWNLOADS")
        print("=" * 70)
        files = db.query(
            "SELECT id, file_name, file_type, download_url FROM files WHERE status = 'failed' LIMIT 50"
        )
        if len(files) > 0:
            print(f"Showing first 50 of {len(files)} failed files:\n")
            for _, row in files.iterrows():
                print(f"  {row['file_name']:50s} ({row['file_type']})")
        else:
            print("No failed downloads.")
        print()
        return

    # Initialize downloader
    downloader = DatasetDownloader(
        db=db,
        output_dir=args.output_dir,
        request_delay=args.delay,
        timeout=args.timeout,
        max_file_size_mb=args.max_file_size_mb,
    )

    # Determine download filters
    extensions = None
    status_filter = "pending"

    if args.download_zip:
        extensions = {"zip"}
        print("=" * 70)
        print("DOWNLOAD PHASE (ZIP files only)")
        print("=" * 70)
    elif args.download_by_type:
        extensions = {args.download_by_type.lower()}
        print("=" * 70)
        print(f"DOWNLOAD PHASE ({args.download_by_type.upper()} files only)")
        print("=" * 70)
    elif args.retry_failed:
        status_filter = "failed"
        print("=" * 70)
        print("DOWNLOAD PHASE (Retrying failed files)")
        print("=" * 70)
    elif args.download_by_status:
        status_filter = args.download_by_status
        print("=" * 70)
        print(f"DOWNLOAD PHASE ({status_filter} files)")
        print("=" * 70)
    else:
        print("=" * 70)
        print("DOWNLOAD PHASE (All files)")
        print("=" * 70)

    print(f"Output directory: {args.output_dir}")
    print(f"Max file size: {args.max_file_size_mb} MB")
    print(f"Timeout: {args.timeout}s")
    print(f"Request delay: {args.delay}s\n")
    print("Starting downloads...\n")

    # Run downloads
    start_time = datetime.now()
    download_stats = downloader.download_all(
        status_filter=status_filter,
        resume=args.resume,
        extensions=extensions,
    )
    elapsed = datetime.now() - start_time

    print(f"\nDownload completed in {elapsed}")
    print(f"  Success: {download_stats['success']}")
    print(f"  Failed:  {download_stats['failed']}")
    print(f"  Skipped: {download_stats['skipped']}\n")

    # Show summary
    stats = db.get_stats()
    print("=" * 70)
    print("DOWNLOAD SUMMARY")
    print("=" * 70)
    print(f"Total projects in database: {stats['total_projects']}")
    print(f"Total files indexed:        {stats['total_files']}\n")
    print("Files by status:")
    total = stats['total_files']
    for status, count in stats['files_by_status'].items():
        pct = 100 * count / total if total > 0 else 0
        print(f"  {status:10s}  {count:4d}  ({pct:5.1f}%)")
    print()

    print("=" * 70)
    print("COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
