from abc import ABC, abstractmethod
from typing import Any


class DocumentExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: str, template_version: str | None = None) -> dict[str, Any]:
        """Extract structured data from a document file."""
        raise NotImplementedError
