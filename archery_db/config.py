# config.py
from enum import Enum
from datetime import date

class Gender(Enum):
    MALE = "Male"
    FEMALE = "Female"

class AgeClass(Enum):
    OPEN = "Open"
    PLUS_50 = "50+"
    PLUS_60 = "60+"
    PLUS_70 = "70+"
    U21 = "Under 21"
    U18 = "Under 18"
    U16 = "Under 16"
    U14 = "Under 14"

class Equipment(Enum):
    RECURVE = "Recurve"
    COMPOUND = "Compound"
    RECURVE_BAREBOW = "Recurve Barebow"
    COMPOUND_BAREBOW = "Compound Barebow"
    LONGBOW = "Longbow"

# Face sizes
FACE_80CM = 80
FACE_120CM = 120  # often written as 122cm in some docs