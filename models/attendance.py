from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

@dataclass
class Attendance:
    student_id: str
    date: str
    time: str
    confidence_score: float
    verification_status: str
    attendance_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: tuple) -> "Attendance":
        return cls(
            attendance_id=row[0],
            student_id=row[1],
            date=row[2],
            time=row[3],
            confidence_score=row[4],
            verification_status=row[5]
        )
