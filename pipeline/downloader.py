import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Optional, Set
from urllib.parse import quote, urlparse

import requests

from clients.dryad_client import DryadClient
from pipeline.database import QDArchDatabase

# By default we download everything EXCEPT media (video / image / audio) and other
# large non-text binaries. Anything not in this set — documents, data, QDA exports,
# code, archives, unknown/extension-less files — is downloaded.
EXCLUDED_EXTENSIONS: Set[str] = {
    # video
    "mp4", "m4v", "mov", "avi", "mkv", "wmv", "flv", "webm", "mpg", "mpeg",
    "3gp", "3g2", "ogv", "mts", "m2ts", "vob",
    # image / photo
    "jpg", "jpeg", "png", "gif", "bmp", "tif", "tiff", "svg", "webp", "heic",
    "heif", "raw", "cr2", "nef", "arw", "psd", "ai", "eps", "ico",
    # audio
    "mp3", "wav", "flac", "aac", "ogg", "oga", "m4a", "wma", "aiff", "aif", "opus",
}

# HTTP statuses worth retrying with backoff (rate limiting / transient server errors).
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Dryad throttles file downloads per IP (auth makes no difference): 100/hour.
# Pace ≥ 3600/100 = 36 s between file downloads, and ≥ 3600/20 = 180 s between
# zip-archive downloads (zip throttle is 20/hour).
_DRYAD_FILE_DELAY = 36.0
_DRYAD_ARCHIVE_DELAY = 180.0


class RateLimitExceeded(Exception):
    """Raised when a rate-limit window won't clear within max_backoff.

    Signals callers to stop hammering the host rather than retry in vain.
    """

    def __init__(self, reset_epoch: float):
        self.reset_epoch = reset_epoch
        super().__init__(f"rate-limit window resets at epoch {int(reset_epoch)}")

# Characters not allowed in Windows path components (also covers control chars).
_ILLEGAL_FS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Longest single filename we'll keep (leaving headroom under Windows' 255 limit).
_MAX_FILENAME_LEN = 200


def _is_junk_member(name: str) -> bool:
    """OS metadata that archives often carry but isn't real content."""
    parts = Path(name).parts
    if "__MACOSX" in parts:
        return True
    base = Path(name).name
    return base in (".DS_Store", "Thumbs.db", "desktop.ini") or base.startswith("._")


def _sanitize_path_part(part: str) -> str:
    """Make one path component safe for the local filesystem (esp. Windows)."""
    if part in ("", ".", ".."):
        return "_"
    part = _ILLEGAL_FS_CHARS.sub("_", part)
    part = part.rstrip(" .")  # Windows forbids trailing spaces/dots
    if len(part) > _MAX_FILENAME_LEN:
        stem, dot, ext = part.rpartition(".")
        if dot and len(ext) <= 10:
            part = stem[: _MAX_FILENAME_LEN - len(ext) - 1] + "." + ext
        else:
            part = part[:_MAX_FILENAME_LEN]
    return part or "_"


# Download status values — aligned to the vocabulary already used in the database
_ST_SUCCESS = "success"
_ST_FAILED = "failed"
_ST_SKIP_SIZE = "skipped_size"        # File too large
_ST_SKIP_EXT = "skipped_ext"          # Wrong extension
_ST_SKIP_EXISTS = "skipped_exists"    # File already exists
_ST_SKIP_NOURL = "skipped_nourl"      # No download URL


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
        max_retries: int = 4,
        max_backoff: float = 300.0,
        dryad_file_delay: float = _DRYAD_FILE_DELAY,
        dryad_archive_delay: float = _DRYAD_ARCHIVE_DELAY,
        zenodo_token: Optional[str] = None,
        figshare_token: Optional[str] = None,
        dryad_client_id: Optional[str] = None,
        dryad_client_secret: Optional[str] = None,
    ):
        self.db = db
        self.output_dir = Path(output_dir)
        # None => download everything except EXCLUDED_EXTENSIONS (media).
        # A set => allowlist (only those extensions), used by --download-zip / --download-by-type.
        self.extensions = extensions
        self.request_delay = request_delay
        self.timeout = timeout
        self.max_retries = max_retries
        # Never sleep longer than this for a single retry; beyond it we bail out
        # of the batch via RateLimitExceeded instead of stalling.
        self.max_backoff = max_backoff
        self.dryad_file_delay = dryad_file_delay
        self.dryad_archive_delay = dryad_archive_delay
        self.max_bytes = int(max_file_size_mb * 1024 * 1024)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Per-repository authentication for downloading restricted/large files.
        self.zenodo_token = zenodo_token
        self.figshare_token = figshare_token
        self._dryad = (
            DryadClient(client_id=dryad_client_id, client_secret=dryad_client_secret)
            if dryad_client_id and dryad_client_secret
            else None
        )

    def _auth_headers(self, url: str) -> Optional[dict]:
        """Return auth headers for the URL's host, or None when unauthenticated."""
        host = urlparse(url).netloc.lower()
        if "zenodo.org" in host and self.zenodo_token:
            return {"Authorization": f"Bearer {self.zenodo_token}"}
        if "figshare.com" in host and self.figshare_token:
            return {"Authorization": f"token {self.figshare_token}"}
        if ("datadryad.org" in host or "dryad.org" in host) and self._dryad:
            return self._dryad._auth_headers()
        return None

    @staticmethod
    def _is_dryad(url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return "datadryad.org" in host or "dryad.org" in host

    def _delay_for(self, url: str) -> float:
        """Per-request pacing — Dryad needs a much larger gap (IP throttle)."""
        return self.dryad_file_delay if self._is_dryad(url) else self.request_delay

    @staticmethod
    def _type_mask(files_df, extensions: Optional[Set[str]]):
        """Boolean mask of files to download.

        extensions is None  -> everything except media (EXCLUDED_EXTENSIONS)
        extensions is a set -> only those extensions (allowlist)
        """
        ftypes = files_df["file_type"].fillna("").str.lower()
        if extensions is not None:
            return ftypes.isin({e.lower() for e in extensions})
        return ~ftypes.isin(EXCLUDED_EXTENSIONS)

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

        # Filter by file type (skip media) and exclude files without URLs
        target = files_df[
            self._type_mask(files_df, extensions)
            & (files_df["download_url"].notna())
            & (files_df["download_url"] != "")
        ]

        tally = {"success": 0, "failed": 0, "skipped": 0}

        if not target.empty:
            for _, file_row in target.iterrows():
                status = self._download_file(
                    file_id=file_row["id"],
                    url=file_row["download_url"],
                    dest=project_dir / _sanitize_path_part(file_row["file_name"]),
                )
                _increment(tally, status)
                time.sleep(self._delay_for(file_row["download_url"]))
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
        extensions     : allowlist of extensions; None => everything except media
        """
        extensions = extensions or self.extensions

        if resume and status_filter:
            files_df = self.db.get_files_by_status(status_filter)
        else:
            files_df = self.db.query("SELECT * FROM files")

        if files_df.empty:
            print("No files to download.")
            return {"success": 0, "failed": 0, "skipped": 0}

        # Filter by file type (skip media unless an explicit allowlist was given)
        target = files_df[self._type_mask(files_df, extensions)]

        if target.empty:
            if extensions is not None:
                print(f"No files match the requested extensions: {extensions}")
            else:
                print("No files to download (all remaining are excluded media types).")
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

            try:
                result = self.download_project(project_id, extensions=extensions)
            except RateLimitExceeded as exc:
                wait_min = max(0, exc.reset_epoch - time.time()) / 60
                print(f"\n[stop] Rate-limit window won't clear for ~{wait_min:.0f} min. "
                      f"Stopping; rerun later to resume (remaining files stay pending).")
                break
            for k in totals:
                totals[k] += result.get(k, 0)

        print(
            f"\nDone. success={totals['success']}  "
            f"failed={totals['failed']}  skipped={totals['skipped']}"
        )
        return totals

    # ── Archive download (Dryad) ────────────────────────────────────────────────

    def download_all_archives(
        self, status_filter: str = "pending", resume: bool = True
    ) -> dict:
        """Download Dryad datasets as single zip archives, then extract them.

        Far cheaper against Dryad's rate limits than per-file downloading: one zip
        request per dataset (zip throttle: 20/hour) instead of one request per file
        (file throttle: 100/hour). Datasets Dryad refuses to zip (too large) fall
        back to per-file downloading. Non-Dryad projects are skipped.
        """
        if resume and status_filter:
            files_df = self.db.get_files_by_status(status_filter)
        else:
            files_df = self.db.query("SELECT * FROM files")

        if files_df.empty:
            print("No files to download.")
            return {"success": 0, "failed": 0, "skipped": 0}

        # Unique project ids, order preserved.
        project_ids = list(dict.fromkeys(files_df["project_id"].tolist()))
        totals = {"success": 0, "failed": 0, "skipped": 0}
        first = True

        for project_id in project_ids:
            project_df = self.db.get_project(project_id)
            if project_df.empty:
                continue
            project = project_df.iloc[0]
            if project["download_repository_folder"] != "dryad" or not project["doi"]:
                continue  # archive download only supported for Dryad datasets

            print(
                f"\n[{project_id}] dryad/{project['download_project_folder']}"
                f" — {project['title'][:60]}"
            )
            if not first:
                time.sleep(self.dryad_archive_delay)  # respect the zip throttle (20/hour)
            first = False

            try:
                result = self.download_project_archive(project_id)
            except RateLimitExceeded as exc:
                wait_min = max(0, exc.reset_epoch - time.time()) / 60
                print(f"\n[stop] Zip rate-limit window won't clear for ~{wait_min:.0f} min. "
                      f"Stopping; rerun later to resume.")
                break
            for k in totals:
                totals[k] += result.get(k, 0)

        print(
            f"\nDone. success={totals['success']}  "
            f"failed={totals['failed']}  skipped={totals['skipped']}"
        )
        return totals

    def download_project_archive(self, project_id: int) -> dict:
        """Download one Dryad dataset as a zip and extract it into the project dir.

        Returns {"success": n, "failed": n, "skipped": n} counted over the
        project's DB file records. Falls back to per-file download when Dryad
        will not assemble the archive.
        """
        project_df = self.db.get_project(project_id)
        if project_df.empty:
            print(f"[{project_id}] not found in database")
            return {"success": 0, "failed": 0, "skipped": 1}
        project = project_df.iloc[0]

        if project["download_repository_folder"] != "dryad" or not project["doi"]:
            print(f"  [{project_id}] archive download only supported for Dryad — using per-file")
            return self.download_project(project_id)

        project_dir = self._project_dir(project)
        project_dir.mkdir(parents=True, exist_ok=True)

        doi = project["doi"]
        archive_url = f"https://datadryad.org/api/v2/datasets/{quote(doi, safe='')}/download"
        zip_path = project_dir / f"_archive_{project['download_project_folder']}.zip"

        outcome = self._download_archive(archive_url, zip_path, name=doi)

        if outcome == "too_large":
            print(f"  [{project_id}] Dryad won't zip this dataset — falling back to per-file")
            return self.download_project(project_id)
        if outcome != "ok":
            return {"success": 0, "failed": 1, "skipped": 0}

        # Extract, then mark matching DB file records as downloaded.
        try:
            members = self._extract_archive(zip_path, project_dir)
        except zipfile.BadZipFile:
            print(f"  [fail] archive for {project_id} is not a valid zip")
            return {"success": 0, "failed": 1, "skipped": 0}
        finally:
            if zip_path.exists():
                zip_path.unlink()  # keep the extracted files, drop the zip itself

        member_basenames = {Path(m).name for m in members}
        files_df = self.db.get_files_for_project(project_id)
        tally = {"success": 0, "failed": 0, "skipped": 0}
        for _, fr in files_df.iterrows():
            if fr["file_name"] in member_basenames:
                self.db.update_file_status(fr["id"], _ST_SUCCESS)
                tally["success"] += 1
            else:
                tally["skipped"] += 1  # in DB but not present in the archive
        print(f"  [ok] extracted {len(members)} files; matched {tally['success']} DB records")
        return tally

    # ── Zip extraction ──────────────────────────────────────────────────────────

    def extract_zips(self, statuses=("success", "skipped_exists")) -> dict:
        """Extract every downloaded .zip on disk and catalog its contents in the DB.

        For each zip file record (file_type 'zip' or name ending '.zip') whose
        download succeeded, the archive is extracted into
        ``<project_dir>/<zipname>_extracted/`` and one ``files`` row is inserted per
        extracted member (status 'extracted', download_url NULL). Re-running is
        idempotent: members already catalogued for the project are not duplicated.
        """
        placeholders = ",".join("?" for _ in statuses)
        zips = self.db.query(
            f"SELECT * FROM files "
            f"WHERE (lower(file_type) = 'zip' OR lower(file_name) LIKE '%.zip') "
            f"AND status IN ({placeholders})",
            tuple(statuses),
        )

        summary = {"zips": 0, "members": 0, "new_entries": 0, "missing": 0, "errors": 0}
        if zips.empty:
            print("No downloaded zip files to extract.")
            return summary

        print(f"Found {len(zips)} downloaded zip file(s).")
        for _, zrow in zips.iterrows():
            project_id = int(zrow["project_id"])
            project_df = self.db.get_project(project_id)
            if project_df.empty:
                continue
            project = project_df.iloc[0]
            project_dir = self._project_dir(project)
            zip_path = project_dir / _sanitize_path_part(zrow["file_name"])

            if not zip_path.exists():
                print(f"  [missing] {zip_path}")
                summary["missing"] += 1
                continue

            extract_subdir = _sanitize_path_part(Path(zrow["file_name"]).stem) + "_extracted"
            extract_dir = project_dir / extract_subdir

            print(f"\n[{project_id}] {zrow['file_name']}")
            try:
                members = self._extract_archive(zip_path, extract_dir)
            except (zipfile.BadZipFile, OSError) as exc:
                print(f"  [error] could not extract — {exc}")
                summary["errors"] += 1
                continue

            summary["zips"] += 1
            summary["members"] += len(members)

            # Existing catalogued members for this project (dedupe across re-runs).
            existing = set(
                self.db.query(
                    "SELECT file_name FROM files WHERE project_id = ? AND status = 'extracted'",
                    (project_id,),
                )["file_name"].tolist()
            )

            new_for_zip = 0
            for member in members:
                rel_name = f"{extract_subdir}/{member}"
                if rel_name in existing:
                    continue
                base = Path(member).name
                ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""
                self.db.insert_file(
                    project_id=project_id,
                    file_name=rel_name,
                    file_type=ext,
                    download_url=None,
                    status="extracted",
                )
                new_for_zip += 1
            summary["new_entries"] += new_for_zip
            print(f"  [ok] {len(members)} members; {new_for_zip} new DB entries")

        return summary

    # ── Internal ──────────────────────────────────────────────────────────────

    def _project_dir(self, project) -> Path:
        """downloads/<repo>/<project>/[<version>/] for a project row."""
        d = (
            self.output_dir
            / project["download_repository_folder"]
            / project["download_project_folder"]
        )
        if project["download_version_folder"]:
            d = d / project["download_version_folder"]
        return d

    def _download_archive(self, url: str, dest_zip: Path, name: str) -> str:
        """Stream a dataset zip to dest_zip. Returns 'ok', 'too_large', or 'failed'.

        Follows Dryad's 302 redirect to pre-signed storage automatically.
        """
        auth = self._auth_headers(url)
        for attempt in range(self.max_retries):
            try:
                with requests.get(url, stream=True, timeout=self.timeout,
                                  headers=auth, allow_redirects=True) as r:
                    if r.status_code == 405:
                        return "too_large"  # Dryad declines to zip oversized datasets
                    if r.status_code in _RETRYABLE_STATUS:
                        self._wait_for_retry(r, attempt, name)
                        continue
                    r.raise_for_status()
                    bytes_written = 0
                    with open(dest_zip, "wb") as fh:
                        for chunk in r.iter_content(chunk_size=65_536):
                            fh.write(chunk)
                            bytes_written += len(chunk)
                print(f"  [ok] archive {name} ({bytes_written / 1024 / 1024:.1f} MB)")
                return "ok"
            except requests.exceptions.RequestException as exc:
                if attempt < self.max_retries - 1:
                    print(f"  [retry] archive {name} — {exc}")
                    if dest_zip.exists():
                        dest_zip.unlink()
                    time.sleep(2 ** attempt)
                    continue
                print(f"  [fail] archive {name} — {exc}")
                if dest_zip.exists():
                    dest_zip.unlink()
                return "failed"
        print(f"  [fail] archive {name} — gave up after {self.max_retries} attempts")
        if dest_zip.exists():
            dest_zip.unlink()
        return "failed"

    @staticmethod
    def _extract_archive(zip_path: Path, dest_dir: Path) -> list:
        """Extract all files of zip_path into dest_dir.

        Each path component is sanitized for the local filesystem (Windows-safe,
        prevents zip-slip). Returns the ORIGINAL member names so callers can match
        them against unmodified DB file names.
        """
        members = []
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                if info.is_dir() or _is_junk_member(info.filename):
                    continue
                members.append(info.filename)
                safe_parts = [_sanitize_path_part(p) for p in Path(info.filename).parts]
                out_path = dest_dir.joinpath(*safe_parts)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(out_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        return members

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

        auth = self._auth_headers(url)
        # Dryad counts a HEAD against the same per-IP download throttle as the GET,
        # so for Dryad we skip the HEAD and size-check from the GET response instead.
        do_head = not self._is_dryad(url)

        for attempt in range(self.max_retries):
            try:
                if do_head:
                    head = requests.head(url, timeout=15, allow_redirects=True, headers=auth)
                    if head.status_code in _RETRYABLE_STATUS:
                        self._wait_for_retry(head, attempt, dest.name)
                        continue
                    content_length = int(head.headers.get("Content-Length", 0))
                    if content_length and content_length > self.max_bytes:
                        size_mb = content_length / 1024 / 1024
                        print(f"  [skip] {dest.name} — {size_mb:.1f} MB exceeds limit")
                        self.db.update_file_status(file_id, _ST_SKIP_SIZE)
                        return _ST_SKIP_SIZE

                # Stream to disk
                with requests.get(url, stream=True, timeout=self.timeout, headers=auth) as r:
                    if r.status_code in _RETRYABLE_STATUS:
                        self._wait_for_retry(r, attempt, dest.name)
                        continue
                    r.raise_for_status()

                    # Size check from the GET response (the only check when HEAD is skipped).
                    content_length = int(r.headers.get("Content-Length", 0))
                    if content_length and content_length > self.max_bytes:
                        size_mb = content_length / 1024 / 1024
                        print(f"  [skip] {dest.name} — {size_mb:.1f} MB exceeds limit")
                        self.db.update_file_status(file_id, _ST_SKIP_SIZE)
                        return _ST_SKIP_SIZE

                    bytes_written = 0
                    oversize = False
                    with open(dest, "wb") as fh:
                        for chunk in r.iter_content(chunk_size=65_536):
                            fh.write(chunk)
                            bytes_written += len(chunk)
                            if bytes_written > self.max_bytes:
                                oversize = True
                                break

                if oversize:
                    print(f"  [skip] {dest.name} — exceeds {self.max_bytes / 1024 / 1024:.0f} MB limit")
                    if dest.exists():
                        dest.unlink()
                    self.db.update_file_status(file_id, _ST_SKIP_SIZE)
                    return _ST_SKIP_SIZE

                size_kb = bytes_written / 1024
                print(f"  [ok] {dest.name} ({size_kb:.1f} KB)")
                self.db.update_file_status(file_id, _ST_SUCCESS)
                return _ST_SUCCESS

            except requests.exceptions.RequestException as exc:
                # Network/timeout errors are transient — back off and retry.
                if attempt < self.max_retries - 1:
                    print(f"  [retry] {dest.name} — {exc}")
                    if dest.exists():
                        dest.unlink()  # remove partial download
                    time.sleep(2 ** attempt)
                    continue
                print(f"  [fail] {dest.name} — {exc}")
                if dest.exists():
                    dest.unlink()
                self.db.update_file_status(file_id, _ST_FAILED)
                return _ST_FAILED

        # Retries exhausted (kept hitting retryable statuses such as 429).
        print(f"  [fail] {dest.name} — gave up after {self.max_retries} attempts")
        if dest.exists():
            dest.unlink()
        self.db.update_file_status(file_id, _ST_FAILED)
        return _ST_FAILED

    def _wait_for_retry(self, response, attempt: int, name: str) -> None:
        """Sleep before a retry, honoring the server's rate-limit signals.

        Dryad sends ``RateLimit-Reset`` (a Unix epoch); others may send
        ``Retry-After`` (seconds). If the required wait exceeds ``max_backoff``
        the window is effectively closed — raise RateLimitExceeded so the caller
        can stop rather than burn retries.
        """
        retry_after = response.headers.get("Retry-After")
        reset = response.headers.get("RateLimit-Reset")
        if retry_after and retry_after.isdigit():
            wait = int(retry_after)
        elif reset and reset.isdigit():
            wait = max(0, int(reset) - int(time.time()))
        else:
            wait = 2 ** attempt  # 1, 2, 4, 8 s

        if wait > self.max_backoff:
            raise RateLimitExceeded(time.time() + wait)

        print(f"  [{response.status_code}] {name} — waiting {wait}s "
              f"(attempt {attempt + 1}/{self.max_retries})")
        time.sleep(wait)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _increment(tally: dict, status: str):
    if status == _ST_SUCCESS:
        tally["success"] += 1
    elif status == _ST_FAILED:
        tally["failed"] += 1
    else:
        tally["skipped"] += 1
