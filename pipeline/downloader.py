import time
from pathlib import Path
from typing import Optional, Set

import requests

from models.record import QDA_EXTENSIONS, QUAL_EXTENSIONS
from pipeline.database import QDArchDatabase

# Extensions downloaded by default: everything that could be qualitative content.
# Excludes pure-code files (.r, .py, .html …) and unwanted binaries.
DEFAULT_EXTENSIONS: Set[str] = QDA_EXTENSIONS | QUAL_EXTENSIONS | {"zip"}

# Download status values stored in the DB
_ST_SUCCESS = "success"
_ST_FAILED = "failed"
_ST_SKIP_SIZE = "skipped_size"
_ST_SKIP_EXT = "skipped_ext"
_ST_SKIP_EXISTS = "skipped_exists"
_ST_SKIP_NOURL = "skipped_no_url"


class DatasetDownloader:
    """
    Downloads files for projects stored in QDArchDatabase.

    Reads from the new schema (projects, files tables) and tracks download status.

    Typical usage
    -------------
    downloader = DatasetDownloader(db)

    # Download all pending files
    downloader.download_all()

    # Only files from a specific project
    downloader.download_project(project_id=123)

    # Resume interrupted downloads
    downloader.download_all(resume=True)
    """

    def __init__(
        self,
        db: QDArchDatabase,
        output_dir: str = "downloads",
        extensions: Optional[Set[str]] = None,
        request_delay: float = 1.0,
        timeout: int = 120,
        max_file_size_mb: float = 500.0,
    ):
        self.db = db
        self.output_dir = Path(output_dir)
        self.extensions = extensions if extensions is not None else DEFAULT_EXTENSIONS
        self.request_delay = request_delay
        self.timeout = timeout
        self.max_bytes = int(max_file_size_mb * 1024 * 1024)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def download_project(
        self, project_id: int, extensions: Optional[Set[str]] = None
    ) -> dict:
        """
        Download all relevant files for one project.
        Returns {"success": n, "failed": n, "skipped": n}.
        """
        extensions = extensions or self.extensions

        projects_df = self.db.get_project(project_id)
        if projects_df.empty:
            print(f"[{project_id}] not found in database")
            return {"success": 0, "failed": 0, "skipped": 1}

        project = projects_df.iloc[0]

        # Build output directory: downloads/<repo>/<project_id>/
        project_dir = (
            self.output_dir
            / project["download_repository_folder"]
            / project["download_project_folder"]
        )
        if project["download_version_folder"]:
            project_dir = project_dir / project["download_version_folder"]

        project_dir.mkdir(parents=True, exist_ok=True)

        # Get all files for this project
        files_df = self.db.get_files_for_project(project_id)

        # Filter by file type and exclude files without URLs
        target = files_df[
            # (files_df["file_type"])
            (files_df["file_type"].isin(extensions))
            & (files_df["download_url"].notna())
            & (files_df["download_url"] != "")
        ]

        tally = {"success": 0, "failed": 0, "skipped": 0}

        if not target.empty:
            for _, file_row in target.iterrows():
                status = self._download_file(
                    file_id=file_row["id"],
                    url=file_row["download_url"],
                    dest=project_dir / file_row["file_name"],
                )
                _increment(tally, status)
                time.sleep(self.request_delay)
        else:
            print(f"  [{project_id}] no matching files (filters: {extensions})")
            tally["skipped"] += len(files_df)

        return tally

    def download_all(
        self,
        status_filter: str = "pending",
        resume: bool = True,
        extensions: Optional[Set[str]] = None,
    ) -> dict:
        """
        Download files for all projects in the DB.

        Parameters
        ----------
        status_filter  : only download files with this status (default: 'pending')
        resume         : if True, skip files already marked success/failed
        extensions     : file extensions to download (default: DEFAULT_EXTENSIONS)
        """
        extensions = extensions or self.extensions

        if resume and status_filter:
            files_df = self.db.get_files_by_status(status_filter)
        else:
            files_df = self.db.query("SELECT * FROM files")

        if files_df.empty:
            print("No files to download.")
            return {"success": 0, "failed": 0, "skipped": 0}

        # Filter by extension
        # target = files_df[files_df["file_type"]]
        target = files_df[files_df["file_type"].isin(extensions)]

        if target.empty:
            print(f"No files match the requested extensions: {extensions}")
            return {"success": 0, "failed": 0, "skipped": len(files_df)}

        print(f"Downloading {len(target)} files...")
        totals = {"success": 0, "failed": 0, "skipped": 0}

        # Group by project for organized downloading
        for project_id, group in target.groupby("project_id"):
            project_df = self.db.get_project(project_id)
            if project_df.empty:
                continue

            project = project_df.iloc[0]
            print(
                f"\n[{project_id}] {project['download_repository_folder']}/{project['download_project_folder']}"
                f" — {project['title'][:60]}"
            )

            result = self.download_project(project_id, extensions=extensions)
            for k in totals:
                totals[k] += result.get(k, 0)

        print(
            f"\nDone. success={totals['success']}  "
            f"failed={totals['failed']}  skipped={totals['skipped']}"
        )
        return totals

    # ── Internal ──────────────────────────────────────────────────────────────

    def _download_file(
        self,
        file_id: int,
        url: str,
        dest: Path,
    ) -> str:
        """
        Download one file with streaming.
        Returns one of the _ST_* status strings.
        """
        # Already on disk
        if dest.exists():
            print(f"  [exists] {dest.name}")
            self.db.update_file_status(file_id, _ST_SKIP_EXISTS)
            return _ST_SKIP_EXISTS

        try:
            # HEAD check: bail out early if the file is too large
            head = requests.head(url, timeout=15, allow_redirects=True)
            content_length = int(head.headers.get("Content-Length", 0))
            if content_length and content_length > self.max_bytes:
                size_mb = content_length / 1024 / 1024
                print(f"  [skip] {dest.name} — {size_mb:.1f} MB exceeds limit")
                self.db.update_file_status(file_id, _ST_SKIP_SIZE)
                return _ST_SKIP_SIZE

            # Stream to disk
            with requests.get(url, stream=True, timeout=self.timeout) as r:
                r.raise_for_status()
                bytes_written = 0
                with open(dest, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=65_536):
                        fh.write(chunk)
                        bytes_written += len(chunk)

            size_kb = bytes_written / 1024
            print(f"  [ok] {dest.name} ({size_kb:.1f} KB)")
            self.db.update_file_status(file_id, _ST_SUCCESS)
            return _ST_SUCCESS

        except Exception as exc:
            print(f"  [fail] {dest.name} — {exc}")
            if dest.exists():
                dest.unlink()  # remove partial download
            self.db.update_file_status(file_id, _ST_FAILED)
            return _ST_FAILED


# ── Helpers ───────────────────────────────────────────────────────────────────

def _increment(tally: dict, status: str):
    if status == _ST_SUCCESS:
        tally["success"] += 1
    elif status == _ST_FAILED:
        tally["failed"] += 1
    else:
        tally["skipped"] += 1
