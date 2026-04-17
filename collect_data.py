#!/usr/bin/env python3
"""
QDArchive Data Collection Pipeline — Extract & Populate Database

This script orchestrates data collection from multiple repositories:
1. Initialize database
2. Set up repository clients
3. Query repositories using configured search terms
4. Filter by open license & relevance
5. Persist metadata to database
6. Export metadata to CSV (optional)

Usage:
    python collect_data.py --help
    python collect_data.py --collect                  # Default: Zenodo + Dryad
    python collect_data.py --collect --figshare       # Add Figshare
    python collect_data.py --collect --cessda         # Add CESSDA
    python collect_data.py --full                     # All repos, all languages
    python collect_data.py --reset                    # Clear database first
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

from params.config import ALL_QUERIES_EN, ALL_QUERIES
from clients.zenodo_client import ZenodoClient
from clients.dryad_client import DryadClient
from clients.cessda_client import CESSDAClient
from clients.figshare_client import FigshareClient
from pipeline.collector import PipelineCollector
from pipeline.database import QDArchDatabase


def main():
    parser = argparse.ArgumentParser(
        description="QDArchive Data Collection Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Core actions
    parser.add_argument(
        "--collect",
        action="store_true",
        help="Run collection queries",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database (destructive)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export metadata to CSV",
    )

    # Repository selection
    parser.add_argument(
        "--figshare",
        action="store_true",
        help="Include Figshare in collection",
    )
    parser.add_argument(
        "--cessda",
        action="store_true",
        help="Include CESSDA in collection",
    )

    # Query options
    parser.add_argument(
        "--max-pages",
        type=int,
        default=3,
        help="Max pages per query (default: 3)",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=25,
        help="Results per page (default: 25)",
    )
    # parser.add_argument(
    #     "--full",
    #     action="store_true",
    #     help="Include all queries (larger scope)",
    # )

    args = parser.parse_args()

    # Show help if no arguments
    if not any([args.collect, args.export, args.reset]):
        parser.print_help()
        return

    # Initialize database
    db_path = "database/23100834-seeding.db"
    db = QDArchDatabase(db_path=db_path)
    print(f"Database: {db_path}\n")

    # Reset if requested
    if args.reset:
        print("Resetting database...")
        db.reset_database()
        print()

    # Run collection
    if args.collect:
        print("=" * 70)
        print("COLLECTION PHASE")
        print("=" * 70)

        # Initialize clients
        zenodo_client = ZenodoClient(timeout=60, access_token="0vhcRrWqQtZVWeT7m8mNI0rnnyIoB4wXSDFQx1iMzgxolGgw6CZcrL2fiXqX")
        dryad_client = DryadClient(timeout=60)
        clients = [zenodo_client, dryad_client]

        if args.cessda:
            cessda_client = CESSDAClient(timeout=60)
            clients.append(cessda_client)

        if args.figshare:
            figshare_client = FigshareClient(timeout=60, access_token="cdff658a362c6b9006a4a037f16e166a8fbd1e4170d688c8fa4d9994b6d2dc1b653dabc3259ef6f847b6519ad3f601db64cdc59200521833bf5751b24fdea166")
            clients.append(figshare_client)

        # Select query set
        # queries = QUERIES_QDA
        queries = ALL_QUERIES
        # queries = ALL_QUERIES if args.full else ALL_QUERIES_EN
        print(f"Running {len(queries)} queries across {len(clients)} repositories...\n")

        # Run collection
        collector = PipelineCollector(clients=clients, db=db, request_delay=5.0)
        # collector = PipelineCollector(clients=clients, db=db)

        start_time = datetime.now()
        records = collector.collect_multi_query(
            queries=queries,
            max_pages=args.max_pages,
            page_size=args.page_size,
            min_relevance=1,
        )
        elapsed = datetime.now() - start_time

        print(f"\nCollection completed in {elapsed}")
        print(f"Collected {len(records)} unique relevant records\n")

    # Show stats
    stats = db.get_stats()
    print("Database Statistics:")
    print(f"  Projects:  {stats['total_projects']}")
    print(f"  Files:     {stats['total_files']}")
    print(f"  Keywords:  {stats['total_keywords']}")
    print(f"  People:    {stats['total_people']}")
    print(f"  Licenses:  {stats['total_licenses']}\n")

    # Export metadata
    if args.export:
        print("=" * 70)
        print("EXPORT PHASE")
        print("=" * 70)

        db.export_projects_csv(path="exports/projects.csv")
        db.export_files_csv(path="exports/files.csv")

        print("Exported:")
        print("  exports/projects.csv")
        print("  exports/files.csv\n")

    print("=" * 70)
    print("COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
