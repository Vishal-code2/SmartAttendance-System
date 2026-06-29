from dataclasses import dataclass, asdict
from typing import Dict, Any

@dataclass
class RiskAssessment:
    student_id: str
    health_score: float
    risk_score: float
    category: str  # Excellent, Good, Warning, Critical

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: tuple) -> "RiskAssessment":
        return cls(
            student_id=row[0],
            health_score=row[1],
            risk_score=row[2],
            category=row[3]
        )
