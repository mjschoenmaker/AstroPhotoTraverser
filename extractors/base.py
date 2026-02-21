from abc import ABC, abstractmethod
from models import SessionMetadata

class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, path) -> SessionMetadata:
        """All extractors must implement this method."""
        pass