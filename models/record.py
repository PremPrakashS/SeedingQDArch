from dataclasses import dataclass, field
from typing import List


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