from dataclasses import dataclass, field
from typing import List

# Extensions that indicate a QDA software export — rare and high-value
QDA_EXTENSIONS = {'qdpx', 'nvpx', 'nvp', 'atlproj', 'mx', 'mx22', 'hpr', 'f4p'}

# Extensions that suggest qualitative text/data files
QUAL_EXTENSIONS = {'docx', 'doc', 'txt', 'rtf', 'odt', 'xlsx', 'csv', 'tsv', 'xml', 'json'}


@dataclass
class FileRecord:
    name: str
    download_url: str
    extension: str = ""


@dataclass
class DatasetRecord:
    source: str
    record_id: str
    title: str
    publication_date: str = ""
    doi: str = ""
    license: str = ""
    record_page: str = ""
    archive_download_link: str = ""
    files: List[FileRecord] = field(default_factory=list)

    @property
    def files_count(self) -> int:
        return len(self.files)

    @property
    def file_names(self) -> List[str]:
        return [f.name for f in self.files]

    @property
    def file_types(self) -> List[str]:
        return sorted(list({f.extension for f in self.files if f.extension}))

    @property
    def has_qda_export(self) -> bool:
        """True if any file is a QDA software project export (.qdpx, .nvpx, etc.)"""
        return any(f.extension in QDA_EXTENSIONS for f in self.files)

    @property
    def has_qual_data(self) -> bool:
        """True if any file has an extension typical of qualitative text/data."""
        return any(f.extension in QUAL_EXTENSIONS for f in self.files)

    @property
    def has_zip(self) -> bool:
        """True if any file is a ZIP archive (contents unknown until inspected)."""
        return any(f.extension == 'zip' for f in self.files)
