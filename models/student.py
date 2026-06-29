from dataclasses import dataclass, asdict
from typing import Dict, Any

@dataclass
class Student:
    student_id: str
    name: str
    roll_no: str
    department: str
    year: str
    division: str
    email: str
    phone: str
    photo_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: tuple) -> "Student":
        return cls(
            student_id=row[0],
            name=row[1],
            roll_no=row[2],
            department=row[3],
            year=row[4],
            division=row[5],
            email=row[6],
            phone=row[7],
            photo_path=row[8] if len(row) > 8 else ""
        )
