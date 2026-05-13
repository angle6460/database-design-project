# main.py
from database import init_db
from models import Archer, Round, RangeDefinition, Score, End
from config import Gender, AgeClass, Equipment
from repositories import ArcherRepository, RoundRepository, ScoreRepository
from datetime import datetime

if __name__ == "__main__":
    init_db()

    # Example Archer
    archer = Archer(first_name="John", last_name="Doe", gender=Gender.MALE,
                    age_class=AgeClass.OPEN, default_equipment=Equipment.RECURVE)
    ArcherRepository.create(archer)

    # Example Round (simplified)
    wa70 = Round(name="WA70/1440", total_arrows=144, possible_score=1440)
    wa70.ranges = [
        RangeDefinition(70, 6, 122),
        RangeDefinition(60, 6, 122),
        RangeDefinition(50, 6, 80),
        RangeDefinition(30, 6, 80),
    ]
    RoundRepository.create(wa70)

    print("Setup complete!")