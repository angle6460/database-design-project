# data_generator.py
import random
from datetime import datetime, timedelta, date
from database import get_connection, init_db
from models import Archer, Round, RangeDefinition, Score, End
from repositories import ArcherRepository, RoundRepository, ScoreRepository
from config import Gender, AgeClass, Equipment


# ---------------------------------------------------------------------------
# Arrow score distributions per equipment type.
# Scores range 0–10 (X counts as 10). Weighted to reflect realistic shooting.
# ---------------------------------------------------------------------------
SCORE_WEIGHTS = {
    Equipment.COMPOUND: [0] * 1 + [1] * 1 + [2] * 1 + [3] * 2 + [4] * 2 + [5] * 3
                        + [6] * 5 + [7] * 8 + [8] * 12 + [9] * 18 + [10] * 27,
    Equipment.RECURVE: [0] * 2 + [1] * 2 + [2] * 3 + [3] * 4 + [4] * 6 + [5] * 8
                       + [6] * 10 + [7] * 14 + [8] * 16 + [9] * 14 + [10] * 10,
    Equipment.RECURVE_BAREBOW: [0] * 3 + [1] * 3 + [2] * 4 + [3] * 6 + [4] * 8 + [5] * 10
                               + [6] * 12 + [7] * 14 + [8] * 12 + [9] * 10 + [10] * 6,
    Equipment.COMPOUND_BAREBOW: [0] * 2 + [1] * 2 + [2] * 3 + [3] * 5 + [4] * 7 + [5] * 9
                                + [6] * 11 + [7] * 14 + [8] * 14 + [9] * 12 + [10] * 8,
    Equipment.LONGBOW: [0] * 5 + [1] * 5 + [2] * 7 + [3] * 9 + [4] * 10 + [5] * 12
                       + [6] * 12 + [7] * 10 + [8] * 9 + [9] * 6 + [10] * 4,
}

# Skill improves slightly with fewer ends remaining (simulate fatigue / form)
DISTANCE_PENALTY = {90: -1.5, 70: -0.8, 60: -0.3, 50: 0, 40: 0.3, 30: 0.5, 20: 0.7}

# ---------------------------------------------------------------------------
# Round definitions
# Each entry: round_name -> list of (distance_m, num_ends, face_size_cm)
# Sourced from the database brief (Archery Australia definitions)
# ---------------------------------------------------------------------------
ROUND_SCHEDULES = {
    # WA / FITA 1440 series (4 ranges, 6 ends each)
    "WA90/1440": [(90, 6, 122), (70, 6, 122), (60, 6, 80), (50, 6, 80)],
    "WA70/1440": [(70, 6, 122), (60, 6, 122), (50, 6, 80), (40, 6, 80)],
    "WA60/1440": [(60, 6, 122), (50, 6, 122), (40, 6, 80), (30, 6, 80)],
    "WA50/1440": [(50, 6, 122), (40, 6, 122), (30, 6, 80), (20, 6, 80)],

    # WA 720 / half-1440 (2 ranges, 6 ends each at same distance)
    "WA720/70": [(70, 6, 122), (70, 6, 122)],
    "WA720/60": [(60, 6, 122), (60, 6, 122)],
    "WA720/50": [(50, 6, 80), (50, 6, 80)],
    "WA720/40": [(40, 6, 80), (40, 6, 80)],
    "WA720/30": [(30, 6, 80), (30, 6, 80)],

    # WA 900 (3 ranges, 5 ends each)
    "WA900": [(60, 5, 122), (50, 5, 122), (40, 5, 80)],

    # Australian city rounds (mostly 3 ranges, mix of 5/6 ends)
    # "36*" = 6 ends (36 arrows) on 80cm; "30+" = 5 ends (30 arrows) on 122cm
    "Sydney": [(70, 6, 80), (60, 6, 80), (50, 6, 80)],
    "Melbourne": [(60, 6, 80), (50, 6, 80), (40, 6, 80)],
    "Brisbane": [(50, 5, 122), (40, 5, 122), (30, 5, 80)],
    "Adelaide": [(40, 6, 80), (30, 6, 80), (20, 6, 80)],
    "Perth": [(60, 5, 122), (50, 5, 122), (40, 5, 80)],
    "Canberra": [(70, 5, 122), (60, 5, 122), (50, 5, 80)],
    "Hobart": [(50, 6, 80), (40, 6, 80), (30, 6, 80)],
    "Darwin": [(30, 6, 80), (20, 6, 80), (20, 6, 80)],
    "Newcastle": [(50, 5, 122), (40, 5, 80), (30, 5, 80)],
    "Wollongong": [(60, 5, 80), (50, 5, 80), (40, 5, 80)],
}

# ---------------------------------------------------------------------------
# Equivalent rounds table (base_round -> {category_key -> equiv_round_name})
# category_key = (gender, age_class, equipment)
# This mirrors what Archery Australia publishes (page 22 of the brief).
# Only a representative subset is listed here; expand as needed.
# ---------------------------------------------------------------------------
EQUIVALENT_ROUNDS = {
    # base round        gender          age_class           equipment           equiv round
    "WA90/1440": {
        (Gender.FEMALE, AgeClass.OPEN, Equipment.RECURVE): "WA70/1440",
        (Gender.MALE, AgeClass.PLUS_50, Equipment.RECURVE): "WA70/1440",
        (Gender.FEMALE, AgeClass.PLUS_50, Equipment.RECURVE): "WA60/1440",
        (Gender.MALE, AgeClass.PLUS_60, Equipment.RECURVE): "WA60/1440",
        (Gender.FEMALE, AgeClass.PLUS_60, Equipment.RECURVE): "WA50/1440",
        (Gender.MALE, AgeClass.U21, Equipment.RECURVE): "WA70/1440",
        (Gender.FEMALE, AgeClass.U21, Equipment.RECURVE): "WA60/1440",
        (Gender.MALE, AgeClass.U18, Equipment.RECURVE): "WA60/1440",
        (Gender.FEMALE, AgeClass.U18, Equipment.RECURVE): "WA50/1440",
        (Gender.MALE, AgeClass.U16, Equipment.RECURVE): "WA50/1440",
        (Gender.FEMALE, AgeClass.U16, Equipment.RECURVE): "WA50/1440",
    },
}

class ArcheryDataGenerator:
    # ------------------------------------------------------------------
    # Name pools
    # ------------------------------------------------------------------
    FIRST_NAMES_FEMALE = [
        "Emma", "Olivia", "Ava", "Charlotte", "Amelia", "Sophie", "Mia",
        "Isabella", "Grace", "Chloe", "Lily", "Zoe", "Hannah", "Ella",
        "Scarlett", "Layla", "Riley", "Aria", "Nora", "Hazel",
    ]
    FIRST_NAMES_MALE = [
        "Liam", "Noah", "Oliver", "Elijah", "James", "William", "Benjamin",
        "Lucas", "Henry", "Alexander", "Mason", "Ethan", "Daniel", "Jack",
        "Logan", "Aiden", "Jackson", "Sebastian", "Mateo", "Owen",
    ]
    LAST_NAMES = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Wilson", "Taylor", "Anderson", "Thomas", "Jackson", "White",
        "Harris", "Martin", "Thompson", "Robinson", "Clark", "Lewis",
        "Walker", "Hall", "Allen", "Young", "Hernandez", "King", "Wright",
        "Lopez", "Hill", "Scott", "Green", "Adams", "Baker", "Nelson",
        "Carter", "Mitchell", "Perez", "Roberts", "Turner", "Phillips",
    ]

    # ------------------------------------------------------------------
    # Age-class -> (min_age, max_age) for DOB generation
    # ------------------------------------------------------------------
    AGE_CLASS_RANGES = {
        AgeClass.U14: (10, 13),
        AgeClass.U16: (14, 15),
        AgeClass.U18: (16, 17),
        AgeClass.U21: (18, 20),
        AgeClass.OPEN: (21, 49),
        AgeClass.PLUS_50: (50, 59),
        AgeClass.PLUS_60: (60, 69),
        AgeClass.PLUS_70: (70, 85),
    }

    def __init__(self):
        init_db()

    # ------------------------------------------------------------------
    # Archers
    # ------------------------------------------------------------------
    def generate_archers(self, count: int = 100) -> list:
        """Create `count` random archers and persist them. Returns list of Archer."""
        archers = []
        today = date.today()

        for _ in range(count):
            gender = random.choice(list(Gender))
            age_class = random.choice(list(AgeClass))
            equipment = random.choice(list(Equipment))

            first_name = random.choice(
                self.FIRST_NAMES_FEMALE if gender == Gender.FEMALE else self.FIRST_NAMES_MALE
            )
            last_name = random.choice(self.LAST_NAMES)

            min_age, max_age = self.AGE_CLASS_RANGES[age_class]
            age_years = random.randint(min_age, max_age)
            dob = today - timedelta(days=age_years * 365 + random.randint(0, 364))

            joined_days_ago = random.randint(30, 365 * 5)
            joined = datetime.now() - timedelta(days=joined_days_ago)

            archer = Archer(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                age_class=age_class,
                default_equipment=equipment,
                date_of_birth=dob,
                joined_date=joined,
            )
            ArcherRepository.create(archer)
            archers.append(archer)

        print(f"✅ Generated {count} archers.")
        return archers

    # ------------------------------------------------------------------
    # Rounds
    # ------------------------------------------------------------------
    def seed_rounds(self) -> dict:
        """Insert all rounds defined in ROUND_SCHEDULES. Returns {name: Round}."""
        seeded = {}
        for name, ranges_data in ROUND_SCHEDULES.items():
            # Skip if already exists
            existing = RoundRepository.get_by_name(name)
            if existing:
                seeded[name] = existing
                continue

            total_arrows = sum(ends * 6 for _, ends, _ in ranges_data)
            possible_score = total_arrows * 10

            round_obj = Round(
                name=name,
                total_arrows=total_arrows,
                possible_score=possible_score,
                ranges=[
                    RangeDefinition(
                        distance=dist,
                        ends=ends,
                        face_size=face,
                        arrows_per_end=6,
                    )
                    for dist, ends, face in ranges_data
                ],
            )
            RoundRepository.create(round_obj)
            seeded[name] = round_obj

        print(f"✅ Seeded {len(seeded)} rounds.")
        return seeded

    def seed_equivalent_rounds(self):
        """
        Insert equivalent-round mappings into the equivalent_rounds table.
        The table must exist (add to init_db if needed):

            CREATE TABLE IF NOT EXISTS equivalent_rounds (
                id INTEGER PRIMARY KEY,
                base_round_id INTEGER NOT NULL,
                equiv_round_id INTEGER NOT NULL,
                gender TEXT NOT NULL,
                age_class TEXT NOT NULL,
                equipment TEXT NOT NULL,
                valid_from DATE,
                valid_to DATE,
                FOREIGN KEY(base_round_id) REFERENCES rounds(id),
                FOREIGN KEY(equiv_round_id) REFERENCES rounds(id)
            )
        """
        conn = get_connection()
        cur = conn.cursor()

        # Ensure table exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS equivalent_rounds (
                id INTEGER PRIMARY KEY,
                base_round_id INTEGER NOT NULL,
                equiv_round_id INTEGER NOT NULL,
                gender TEXT NOT NULL,
                age_class TEXT NOT NULL,
                equipment TEXT NOT NULL,
                valid_from DATE,
                valid_to DATE,
                FOREIGN KEY(base_round_id) REFERENCES rounds(id),
                FOREIGN KEY(equiv_round_id) REFERENCES rounds(id)
            )
        """)

        rows_inserted = 0
        for base_name, mappings in EQUIVALENT_ROUNDS.items():
            base = RoundRepository.get_by_name(base_name)
            if not base:
                continue
            for (gender, age_class, equipment), equiv_name in mappings.items():
                equiv = RoundRepository.get_by_name(equiv_name)
                if not equiv:
                    continue
                cur.execute("""
                    INSERT OR IGNORE INTO equivalent_rounds
                        (base_round_id, equiv_round_id, gender, age_class, equipment, valid_from)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (base.id, equiv.id,
                      gender.value, age_class.value, equipment.value,
                      date.today().isoformat()))
                rows_inserted += 1

        conn.commit()
        conn.close()
        print(f"✅ Seeded {rows_inserted} equivalent-round mappings.")

    # ------------------------------------------------------------------
    # Score generation helpers
    # ------------------------------------------------------------------
    def _random_arrow(self, equipment: Equipment, distance: int) -> int:
        """
        Return a single random arrow score (0-10) for given equipment and distance.
        Longer distances apply a small negative bias.
        """
        pool = SCORE_WEIGHTS[equipment]
        base = random.choice(pool)
        penalty = DISTANCE_PENALTY.get(distance, 0)
        # Shift score by penalty; clamp to [0, 10]
        score = round(base + penalty + random.gauss(0, 0.5))
        return max(0, min(10, score))

    def _generate_end(
            self,
            end_number: int,
            range_number: int,
            distance: int,
            equipment: Equipment,
            arrows_per_end: int = 6,
    ) -> End:
        """Generate one end of arrows, sorted highest to lowest (as per rules)."""
        arrows = sorted(
            [self._random_arrow(equipment, distance) for _ in range(arrows_per_end)],
            reverse=True,
        )
        return End(end_number=end_number, range_number=range_number, arrows=arrows)

    # ------------------------------------------------------------------
    # Generate a single score for an archer on a round
    # ------------------------------------------------------------------
    def generate_random_score(
            self,
            archer_id: int,
            round_id: int,
            equipment: Equipment = None,
            date_shot: datetime = None,
            is_competition: bool = False,
            competition_id: int = None,
            notes: str = "",
    ) -> Score:
        """
        Generate a realistic randomised score for an archer on a round.
        Saves to the database and returns the Score object.
        """
        archer = ArcherRepository.get_by_id(archer_id)
        round_obj = RoundRepository.get_by_id(round_id)

        if not archer or not round_obj:
            raise ValueError(f"Archer {archer_id} or Round {round_id} not found.")

        if equipment is None:
            equipment = archer.default_equipment
        if date_shot is None:
            date_shot = datetime.now() - timedelta(days=random.randint(0, 365 * 2))

        ends = []
        total_score = 0

        for range_number, range_def in enumerate(round_obj.ranges, start=1):
            for end_number in range(1, range_def.ends + 1):
                end = self._generate_end(
                    end_number=end_number,
                    range_number=range_number,
                    distance=range_def.distance,
                    equipment=equipment,
                    arrows_per_end=range_def.arrows_per_end,
                )
                ends.append(end)
                total_score += sum(end.arrows)

        score = Score(
            archer_id=archer_id,
            round_id=round_id,
            equipment=equipment,
            date_shot=date_shot,
            is_competition=is_competition,
            competition_id=competition_id,
            total_score=total_score,
            ends=ends,
            notes=notes,
        )
        ScoreRepository.save(score)
        return score

    # ------------------------------------------------------------------
    # Bulk score generation
    # ------------------------------------------------------------------
    def generate_scores_for_all_archers(
            self,
            rounds: dict,
            scores_per_archer: int = 10,
    ) -> int:
        """
        For every archer in the DB, generate `scores_per_archer` random practice
        scores spread across rounds proportional to the archer's age class.
        Returns total number of scores generated.
        """
        archers = ArcherRepository.list_all()
        round_names = list(rounds.keys())
        total = 0

        for archer in archers:
            for _ in range(scores_per_archer):
                round_obj = rounds[random.choice(round_names)]
                if round_obj.id is None:
                    continue
                try:
                    self.generate_random_score(
                        archer_id=archer.id,
                        round_id=round_obj.id,
                        equipment=archer.default_equipment,
                    )
                    total += 1
                except Exception as e:
                    print(f"  ⚠️  Skipped score for archer {archer.id}: {e}")

        print(f"✅ Generated {total} practice scores.")
        return total

    # ------------------------------------------------------------------
    # Competition generation
    # ------------------------------------------------------------------
    def generate_competitions(
            self,
            rounds: dict,
            num_competitions: int = 6,
            archers_per_comp: int = 20,
            is_championship: bool = False,
    ) -> list:
        """
        Create `num_competitions` competitions, each using a random round,
        with random archers shooting scores.  Returns list of competition IDs.
        """
        conn = get_connection()
        cur = conn.cursor()

        # Ensure competitions table has is_championship column (already in schema)
        all_archers = ArcherRepository.list_all()
        round_names = list(rounds.keys())
        comp_ids = []

        comp_names = [
            "Club Monthly Shoot", "State Qualifier", "Spring Open",
            "Autumn Classic", "Indoor Championship", "Club Interclub",
            "Winter Series", "Summer League", "Junior Cup", "Masters Invitational",
        ]

        for i in range(num_competitions):
            round_name = random.choice(round_names)
            round_obj = rounds[round_name]
            if round_obj.id is None:
                continue

            comp_date = date.today() - timedelta(days=random.randint(0, 365))
            name = f"{random.choice(comp_names)} {comp_date.year}"

            cur.execute("""
                INSERT INTO competitions (name, date, round_id, is_championship)
                VALUES (?, ?, ?, ?)
            """, (name, comp_date.isoformat(), round_obj.id, int(is_championship)))
            comp_id = cur.lastrowid
            conn.commit()
            comp_ids.append(comp_id)

            # Pick random subset of archers for this competition
            participants = random.sample(all_archers, min(archers_per_comp, len(all_archers)))
            for archer in participants:
                try:
                    self.generate_random_score(
                        archer_id=archer.id,
                        round_id=round_obj.id,
                        equipment=archer.default_equipment,
                        date_shot=datetime.combine(comp_date, datetime.min.time()),
                        is_competition=True,
                        competition_id=comp_id,
                    )
                except Exception as e:
                    print(f"  ⚠️  Skipped comp score for archer {archer.id}: {e}")

        conn.close()
        print(f"✅ Generated {len(comp_ids)} competitions.")
        return comp_ids

    # ------------------------------------------------------------------
    # Full seed: run everything in order
    # ------------------------------------------------------------------
    def seed_all(
            self,
            num_archers: int = 100,
            scores_per_archer: int = 10,
            num_competitions: int = 8,
    ):
        """Convenience method to seed the entire database from scratch."""
        print("🏹 Seeding rounds...")
        rounds = self.seed_rounds()

        print("🏹 Seeding equivalent rounds...")
        self.seed_equivalent_rounds()

        print("🏹 Generating archers...")
        self.generate_archers(num_archers)

        print("🏹 Generating practice scores...")
        self.generate_scores_for_all_archers(rounds, scores_per_archer)

        print("🏹 Generating competitions...")
        self.generate_competitions(rounds, num_competitions)

        print("\n✅ Database seeding complete!")
if __name__ == '__main__':

    data_generator = ArcheryDataGenerator()
    data_generator.seed_all()