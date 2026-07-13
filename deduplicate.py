#!/usr/bin/env python3
"""
QDArchive Deduplication — collapse projects harvested more than once.

The collector runs one search per query string ("focus group", "grounded
theory", "analyse thematique", ...). A dataset matching N of those queries was
inserted N times, so the same repository record exists as N project rows that
differ only in `query_string` and `id`.

Identity is the repository record itself, keyed on project_url (falling back to
doi, then repository/folder/version). One survivor per group is kept — the row
with the most extracted text, then the most files, then the lowest id — and the
rest are deleted with their files/keywords/people/licences/classifications via
ON DELETE CASCADE.

Database only: nothing under downloads/ or extracted_text/ is touched. That is
also the safe choice, since duplicates share their downloads with the survivor
(every copy points at the same downloads/figshare/<article>/<file>), so deleting
by project id would take the survivor's data with it.

Usage:
    python deduplicate.py                 # dry run: report only, no changes
    python deduplicate.py --apply         # perform the deletion (backs up first)
    python deduplicate.py --manifest dedupe.csv      # write per-group decisions
"""
import argparse
import csv
import sqlite3
import sys
from collections import defaultdict

# UTF-8 console so printing non-cp1252 titles doesn't crash on Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

DB_PATH = "database/23100834-seeding.db"


def identity_key(row) -> str | None:
    """The repository record this project row came from.

    project_url is the strongest signal; doi and the download folder triple are
    fallbacks for rows that lack it. Returns None when the row carries no usable
    identity — such a row is never grouped, so it is never deleted.
    """
    for candidate in (row["project_url"], row["doi"]):
        if candidate and candidate.strip():
            return candidate.strip().lower()
    if row["repository_id"] is not None and row["download_project_folder"]:
        return (
            f"{row['repository_id']}|{row['download_project_folder']}"
            f"|{row['version'] or ''}"
        ).lower()
    return None


def find_duplicate_groups(conn) -> list[tuple[str, int, list[int]]]:
    """Group project rows by repository identity.

    Returns (key, survivor_id, [ids_to_delete]) for every group with >1 row.
    """
    rows = conn.execute(
        """
        SELECT p.id, p.project_url, p.doi, p.repository_id,
               p.download_project_folder, p.version, p.title,
               (SELECT COUNT(*) FROM extracted_texts et WHERE et.project_id = p.id) AS n_text,
               (SELECT COUNT(*) FROM files f WHERE f.project_id = p.id) AS n_files
        FROM projects p
        ORDER BY p.id
        """
    ).fetchall()

    groups: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        key = identity_key(row)
        if key:
            groups[key].append(row)

    duplicates = []
    for key, members in groups.items():
        if len(members) < 2:
            continue
        # Keep the richest row: most extracted text, then most files, then the
        # earliest harvest. Duplicates are usually identical, so this is mostly
        # a deterministic tiebreak — but it protects against a partially
        # downloaded copy winning over a complete one.
        ranked = sorted(members, key=lambda r: (-r["n_text"], -r["n_files"], r["id"]))
        survivor = ranked[0]
        duplicates.append((key, survivor["id"], [r["id"] for r in ranked[1:]]))

    return duplicates


def write_manifest(path: str, conn, groups) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["identity_key", "survivor_id", "deleted_id", "title", "query_string"])
        for key, survivor, doomed in groups:
            for pid in doomed:
                row = conn.execute(
                    "SELECT title, query_string FROM projects WHERE id=?", (pid,)
                ).fetchone()
                writer.writerow([key, survivor, pid, row["title"], row["query_string"]])
    print(f"Manifest written: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove duplicate project rows from the QDArch database"
    )
    parser.add_argument("--db", default=DB_PATH, help=f"SQLite database (default: {DB_PATH})")
    parser.add_argument("--apply", action="store_true",
                        help="Perform the deletion (default is a dry run)")
    parser.add_argument("--no-backup", action="store_true",
                        help="Skip the database backup taken before deleting")
    parser.add_argument("--manifest", help="Write per-group keep/delete decisions to this CSV")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    groups = find_duplicate_groups(conn)
    doomed = {pid for _, _, ids in groups for pid in ids}

    print(f"Projects in database:  {total}")
    print(f"Duplicate groups:      {len(groups)}")
    print(f"Redundant rows:        {len(doomed)}")
    print(f"Projects remaining:    {total - len(doomed)}")

    if not doomed:
        print("\nNothing to do — no duplicates found.")
        return 0

    for table in ("files", "keywords", "person_role", "licenses",
                  "relevance_scores", "extracted_texts", "classifications"):
        ids = sorted(doomed)
        n = sum(
            conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE project_id IN "
                f"({','.join('?' * len(chunk))})", chunk
            ).fetchone()[0]
            for chunk in (ids[i:i + 500] for i in range(0, len(ids), 500))
        )
        print(f"  cascade -> {table:<18} {n} rows")

    if args.manifest:
        write_manifest(args.manifest, conn, groups)

    if not args.apply:
        print("\nDRY RUN — nothing changed. Re-run with --apply to delete.")
        print("\nSample of what would be removed:")
        for _key, survivor, ids in groups[:5]:
            title = conn.execute(
                "SELECT title FROM projects WHERE id=?", (survivor,)
            ).fetchone()["title"]
            print(f"  keep {survivor}, drop {len(ids)} copies — {(title or '')[:60]}")
        return 0

    if not args.no_backup:
        from classify.backup import backup_database
        backup = backup_database(args.db)
        print(f"\nBackup: {backup}")

    # CASCADE is what removes files/keywords/person_role/licenses/
    # relevance_scores/extracted_texts/classifications — and SQLite leaves
    # foreign keys OFF by default, so this pragma is load-bearing, not decoration.
    conn.execute("PRAGMA foreign_keys = ON")
    if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        print("ERROR: could not enable foreign keys; aborting rather than orphaning rows.")
        return 1

    ids = sorted(doomed)
    with conn:
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            conn.execute(
                f"DELETE FROM projects WHERE id IN ({','.join('?' * len(chunk))})", chunk
            )
    print(f"Deleted {len(ids)} project rows (cascaded to files, keywords, people, "
          f"licences, relevance scores, extracted texts, classifications).")

    remaining = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    print(f"Projects now in database: {remaining}")

    conn.execute("VACUUM")
    print("Database vacuumed.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
