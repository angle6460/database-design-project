# data_generator.py
import random
from datetime import datetime, timedelta
from .database import get_connection
from .models import Archer, Round, RangeDefinition
from .repositories import ArcherRepository, RoundRepository, ScoreRepository
from .config import Gender, AgeClass, Equipment

class ArcheryDataGenerator:
    def __init__(self):
        self.first_names = ['Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Oliver', 'Charlotte', ...]  # your list
        self.last_names = ['Smith', 'Johnson', ...]

        self.round_schedules = {
            "WA90/1440": [(90,6,122),(70,6,122),(60,6,80),(50,6,80)],
            "WA70/1440": [(70,6,122),(60,6,122),(50,6,80),(40,6,80)],
            # need to finish
        }

    def generate_archers(self, count=100):
        for _ in range(count):
            archer = Archer(
                first_name=random.choice(self.first_names),
                last_name=random.choice(self.last_names),
                gender=random.choice(list(Gender)),
                age_class=random.choice(list(AgeClass)),
                default_equipment=random.choice(list(Equipment))
            )
            ArcherRepository.create(archer)

    def seed_rounds(self):
        for name, ranges_data in self.round_schedules.items():
            round_obj = Round(name=name, total_arrows=sum(e*6 for e,_,_ in ranges_data),
                              possible_score=10*sum(e*6 for e,_,_ in ranges_data))
            round_obj.ranges = [RangeDefinition(d, ends, face) for d, ends, face in ranges_data]
            RoundRepository.create(round_obj)

    def generate_random_score(self, archer_id: int, round_id: int):
        # Complex logic to generate realistic ends...
        pass  # I can expand this