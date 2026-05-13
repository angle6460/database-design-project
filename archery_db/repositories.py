# repositories.py
from typing import List, Optional
from datetime import datetime
from database import get_connection
from models import Archer, Round, Score, End, Gender, AgeClass, RangeDefinition
from config import Equipment


class ArcherRepository:

    @staticmethod
    def create(archer: Archer) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO archers (first_name, last_name, gender, age_class, default_equipment, date_of_birth)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (archer.first_name, archer.last_name, archer.gender.value,
              archer.age_class.value, archer.default_equipment.value, archer.date_of_birth))
        conn.commit()
        archer.id = cur.lastrowid
        conn.close()
        return archer.id

    @staticmethod
    def get_by_id(archer_id: int) -> Optional[Archer]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM archers WHERE id = ?", (archer_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            data = dict(row)
            return Archer(
                id=data['id'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                gender=Gender(data['gender']),
                age_class=AgeClass(data['age_class']),
                default_equipment=Equipment(data['default_equipment']),
                date_of_birth=data['date_of_birth']
            )
        return None

    @staticmethod
    def list_all() -> List[Archer]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM archers ORDER BY last_name, first_name")
        rows = cur.fetchall()
        conn.close()
        archers = []
        for row in rows:
            data = dict(row)
            archers.append(Archer(
                id=data['id'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                gender=Gender(data['gender']),
                age_class=AgeClass(data['age_class']),
                default_equipment=Equipment(data['default_equipment']),
                date_of_birth=data['date_of_birth']
            ))
        return archers

class RoundRepository:

    @staticmethod
    def create(round_obj: Round) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO rounds (name, total_arrows, possible_score, valid_from, valid_to)
            VALUES (?, ?, ?, ?, ?)
        """, (round_obj.name, round_obj.total_arrows, round_obj.possible_score,
              round_obj.valid_from, round_obj.valid_to))
        round_id = cur.lastrowid

        for i, r in enumerate(round_obj.ranges, 1):
            cur.execute("""
                INSERT INTO round_ranges (round_id, range_number, distance, ends, face_size)
                VALUES (?, ?, ?, ?, ?)
            """, (round_id, i, r.distance, r.ends, r.face_size))

        conn.commit()
        conn.close()
        return round_id

    @staticmethod
    def get_by_id(round_id: int) -> Optional[Round]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM rounds WHERE id = ?", (round_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return None

        round_obj = Round(**dict(row))

        cur.execute("""
                SELECT * FROM round_ranges 
                WHERE round_id = ? 
                ORDER BY range_number
            """, (round_id,))
        for r in cur.fetchall():
            round_obj.ranges.append(RangeDefinition(**dict(r)))

        conn.close()
        return round_obj

    @staticmethod
    def get_by_name(name: str) -> Optional[Round]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM rounds WHERE name = ?", (name,))
        row = cur.fetchone()
        conn.close()
        if row:
            return RoundRepository.get_by_id(row['id'])
        return None

class ScoreRepository:

    @staticmethod
    def save(score: Score) -> int:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO scores (archer_id, round_id, equipment, date_shot, is_competition,
                                competition_id, total_score, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (score.archer_id, score.round_id, score.equipment.value,
              score.date_shot.isoformat(), int(score.is_competition),
              score.competition_id, score.total_score, score.notes))

        score_id = cur.lastrowid

        for end in score.ends:
            arrows = end.arrows + [None] * (6 - len(end.arrows))  # pad to 6
            cur.execute("""
                INSERT INTO score_ends (score_id, range_number, end_number,
                                        arrow1, arrow2, arrow3, arrow4, arrow5, arrow6)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (score_id, end.range_number, end.end_number, *arrows))

        conn.commit()
        conn.close()
        return score_id

    @staticmethod
    def get_by_archer(archer_id: int, limit: int = 50) -> List[Score]:
        # TODO: Implement with joins to get full score + ends
        pass
