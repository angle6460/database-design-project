# models.py
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Optional
from config import Equipment, Gender, AgeClass

@dataclass
class Archer:
    id: Optional[int] = None
    first_name: str = ""
    last_name: str = ""
    gender: Gender = Gender.MALE
    age_class: AgeClass = AgeClass.OPEN
    default_equipment: Equipment = Equipment.RECURVE
    date_of_birth: Optional[date] = None
    joined_date: datetime = field(default_factory=datetime.now)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

@dataclass
class RangeDefinition:
    distance: int          # metres
    ends: int              # 5 or 6
    face_size: int         # 80 or 120
    arrows_per_end: int = 6

@dataclass
class Round:
    id: Optional[int] = None
    name: str = ""                    # e.g. "WA70/1440", "Sydney"
    total_arrows: int = 0
    possible_score: int = 0
    ranges: List[RangeDefinition] = field(default_factory=list)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

@dataclass
class End:
    end_number: int                   # within a range
    range_number: int                 # which range in the round
    arrows: List[int] = field(default_factory=list)   # 6 scores, sorted high to low

@dataclass
class Score:
    id: Optional[int] = None
    archer_id: int = 0
    round_id: int = 0
    equipment: Equipment = Equipment.RECURVE
    date_shot: datetime = field(default_factory=datetime.now)
    is_competition: bool = False
    competition_id: Optional[int] = None
    total_score: int = 0
    ends: List[End] = field(default_factory=list)
    notes: str = ""