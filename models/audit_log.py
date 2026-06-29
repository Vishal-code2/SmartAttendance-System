from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

@dataclass
class AuditLog:
    timestamp: str
    action: str
    user: str
    log_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: tuple) -> "AuditLog":
        return cls(
            log_id=row[0],
            timestamp=row[1],
            action=row[2],
            user=row[3]
        )
