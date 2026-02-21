from dataclasses import dataclass
from typing import Optional

@dataclass
class SessionMetadata:
    camera: Optional[str] = None
    filter: Optional[str] = None
    gain: Optional[str] = None
    exposure: Optional[str] = None
    temperature: Optional[str] = None