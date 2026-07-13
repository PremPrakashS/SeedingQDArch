import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="classify",
        description="ISIC Rev. 5 classification pipeline for QDArch projects",
    )
    parser.add_argument(
        "--db",
        default="database/23100834-seeding.db",
        help="Path to SQLite database (default: database/23100834-seeding.db)",
    )
    parser.add_argument(
        "--projects",
        help="Comma-separated project IDs to classify, e.g. 11,15,20",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="run_all",
        help="Classify all projects in the database",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of results to write to DB in one transaction (default: 50)",
    )
    parser.add_argument(
        "--output-dir",
        default="classify_output",
        help="Directory for reports and logs (default: classify_output)",
    )
    parser.add_argument(
        "--skip-context",
        action="store_true",
        help="Skip downloading content files; use only DB metadata",
    )
    parser.add_argument(
        "--skip-summary",
        action="store_true",
        help="Skip LLM summarisation; use title+keywords as classification input",
    )
    parser.add_argument(
        "--type",
        dest="project_types",
        help=(
            "Only classify projects of these types (comma-separated): "
            "QDA_PROJECT, QD_PROJECT, OTHER_PROJECT, NOT_A_PROJECT"
        ),
    )
    parser.add_argument(
        "--per-file",
        action="store_true",
        dest="per_file",
        help="Also classify each primary data file individually (embedder-only, uses extracted text)",
    )
    parser.add_argument(
        "--no-rerank",
        action="store_false",
        dest="rerank",
        help="Disable the LLM re-ranker on NEEDS_REVIEW projects (rerank is on by default when the LLM is loaded)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_false",
        dest="backup",
        help="Skip the automatic database backup taken before the run",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run full pipeline but do not write results to DB",
    )
    parser.add_argument(
        "--migrate-only",
        action="store_true",
        help="Apply schema migration and exit",
    )

    args = parser.parse_args()

    if args.migrate_only:
        from classify import schema
        if args.backup:
            from classify.backup import backup_database
            bk = backup_database(args.db)
            if bk:
                print(f"Backup: {bk}")
        ops = schema.migrate(args.db)
        print("Migration applied:", ops if ops else "already up to date")
        sys.exit(0)

    if not args.projects and not args.run_all:
        parser.error("Specify --projects IDs (e.g. --projects 11,15,20) or --all")

    project_ids = None
    if args.projects:
        try:
            project_ids = [int(x.strip()) for x in args.projects.split(",") if x.strip()]
        except ValueError as exc:
            parser.error(f"Invalid project IDs: {exc}")

    project_types = None
    if args.project_types:
        valid_types = {"QDA_PROJECT", "QD_PROJECT", "OTHER_PROJECT", "NOT_A_PROJECT"}
        project_types = [t.strip().upper() for t in args.project_types.split(",") if t.strip()]
        unknown = set(project_types) - valid_types
        if unknown:
            parser.error(f"Invalid project types: {sorted(unknown)} (valid: {sorted(valid_types)})")

    from classify.pipeline import ClassifyPipeline

    pipeline = ClassifyPipeline(
        db_path=args.db,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        skip_context=args.skip_context,
        skip_summary=args.skip_summary,
        dry_run=args.dry_run,
        project_types=project_types,
        per_file=args.per_file,
        rerank=args.rerank,
        backup=args.backup,
    )

    stats = pipeline.run(project_ids)

    print("\n=== Classification complete ===")
    print(f"Total projects: {stats['total']}")
    print(f"Processed:      {stats['processed']}")
    for status, count in sorted(stats["status_counts"].items()):
        print(f"  {status:<20} {count}")
    if stats.get("reranked"):
        print(f"Re-ranked (NEEDS_REVIEW): {stats['reranked']}, "
              f"rescued to ACCEPTED: {stats['rerank_rescued']}")
    if stats.get("files_processed"):
        print(f"Files classified: {stats['files_processed']}")
        for status, count in sorted(stats["file_status_counts"].items()):
            print(f"  {status:<20} {count}")
    if stats.get("backup_path"):
        print(f"Backup: {stats['backup_path']}")
    if stats["report_paths"]:
        print("\nReports:")
        for name, path in stats["report_paths"].items():
            print(f"  {name}: {path}")
    print(f"Log: {stats['log_path']}")


if __name__ == "__main__":
    main()
