# repositories.py
from typing import List, Optional
from datetime import datetime, date
from database import get_connection
from models import Archer, Round, Score, End, RangeDefinition
from config import Equipment, Gender, AgeClass


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
                date_of_birth=data['date_of_birth'],
            )
        return None

    @staticmethod
    def list_all() -> List[Archer]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM archers ORDER BY last_name, first_name")
        rows = cur.fetchall()
        conn.close()
        return [
            Archer(
                id=dict(row)['id'],
                first_name=dict(row)['first_name'],
                last_name=dict(row)['last_name'],
                gender=Gender(dict(row)['gender']),
                age_class=AgeClass(dict(row)['age_class']),
                default_equipment=Equipment(dict(row)['default_equipment']),
                date_of_birth=dict(row)['date_of_birth'],
            )
            for row in rows
        ]

    @staticmethod
    def update(archer: Archer) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE archers
            SET first_name=?, last_name=?, gender=?, age_class=?, default_equipment=?, date_of_birth=?
            WHERE id=?
        """, (archer.first_name, archer.last_name, archer.gender.value,
              archer.age_class.value, archer.default_equipment.value,
              archer.date_of_birth, archer.id))
        conn.commit()
        updated = cur.rowcount > 0
        conn.close()
        return updated

    @staticmethod
    def delete(archer_id: int) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM archers WHERE id = ?", (archer_id,))
        conn.commit()
        deleted = cur.rowcount > 0
        conn.close()
        return deleted

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
        round_obj.id = round_id

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

        data = dict(row)
        round_obj = Round(
            id=data['id'],
            name=data['name'],
            total_arrows=data['total_arrows'],
            possible_score=data['possible_score'],
            valid_from=data.get('valid_from'),
            valid_to=data.get('valid_to'),
        )

        cur.execute("""
            SELECT * FROM round_ranges
            WHERE round_id = ?
            ORDER BY range_number
        """, (round_id,))
        for r in cur.fetchall():
            rd = dict(r)
            round_obj.ranges.append(RangeDefinition(
                distance=rd['distance'],
                ends=rd['ends'],
                face_size=rd['face_size'],
                arrows_per_end=6,
            ))

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

    @staticmethod
    def list_all() -> List[Round]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM rounds ORDER BY name")
        rows = cur.fetchall()
        conn.close()
        return [RoundRepository.get_by_id(row['id']) for row in rows]

    @staticmethod
    def get_equivalent_round(
            base_round_id: int,
            gender: Gender,
            age_class: AgeClass,
            equipment: Equipment,
            as_of: Optional[date] = None,
    ) -> Optional[Round]:
        """
        Look up the equivalent round for a given base round and archer category.
        Respects valid_from / valid_to dating so historical competitions remain valid.
        """
        if as_of is None:
            as_of = date.today()

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT equiv_round_id FROM equivalent_rounds
            WHERE base_round_id = ?
              AND gender      = ?
              AND age_class   = ?
              AND equipment   = ?
              AND (valid_from IS NULL OR valid_from <= ?)
              AND (valid_to   IS NULL OR valid_to   >= ?)
            ORDER BY valid_from DESC
            LIMIT 1
        """, (base_round_id, gender.value, age_class.value, equipment.value,
              as_of.isoformat(), as_of.isoformat()))
        row = cur.fetchone()
        conn.close()
        if row:
            return RoundRepository.get_by_id(row['equiv_round_id'])
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
        score.id = score_id

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
    def _row_to_score(row: dict) -> Score:
        return Score(
            id=row['id'],
            archer_id=row['archer_id'],
            round_id=row['round_id'],
            equipment=Equipment(row['equipment']),
            date_shot=datetime.fromisoformat(row['date_shot']),
            is_competition=bool(row['is_competition']),
            competition_id=row['competition_id'],
            total_score=row['total_score'],
            notes=row['notes'] or "",
        )

    @staticmethod
    def _load_ends(score_id: int, cur) -> List[End]:
        cur.execute("""
            SELECT * FROM score_ends
            WHERE score_id = ?
            ORDER BY range_number, end_number
        """, (score_id,))
        ends = []
        for r in cur.fetchall():
            rd = dict(r)
            arrows = [
                rd[col] for col in ('arrow1', 'arrow2', 'arrow3', 'arrow4', 'arrow5', 'arrow6')
                if rd[col] is not None
            ]
            ends.append(End(
                end_number=rd['end_number'],
                range_number=rd['range_number'],
                arrows=arrows,
            ))
        return ends

    @staticmethod
    def get_by_id(score_id: int) -> Optional[Score]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM scores WHERE id = ?", (score_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return None
        score = ScoreRepository._row_to_score(dict(row))
        score.ends = ScoreRepository._load_ends(score_id, cur)
        conn.close()
        return score

    @staticmethod
    def get_by_archer(
            archer_id: int,
            limit: int = 50,
            round_id: Optional[int] = None,
            from_date: Optional[datetime] = None,
            to_date: Optional[datetime] = None,
            sort_by: str = "date",  # "date" | "score"
            sort_desc: bool = True,
    ) -> List[Score]:
        """
        Return scores for an archer with optional filtering and sorting.
        Supports date range, round filter, and sort by date or total_score.
        Ends are loaded for each score.
        """
        conn = get_connection()
        cur = conn.cursor()

        clauses = ["archer_id = ?"]
        params: list = [archer_id]

        if round_id is not None:
            clauses.append("round_id = ?")
            params.append(round_id)
        if from_date is not None:
            clauses.append("date_shot >= ?")
            params.append(from_date.isoformat())
        if to_date is not None:
            clauses.append("date_shot <= ?")
            params.append(to_date.isoformat())

        order_col = "total_score" if sort_by == "score" else "date_shot"
        order_dir = "DESC" if sort_desc else "ASC"

        query = f"""
            SELECT * FROM scores
            WHERE {' AND '.join(clauses)}
            ORDER BY {order_col} {order_dir}
            LIMIT ?
        """
        params.append(limit)
        cur.execute(query, params)
        rows = cur.fetchall()

        scores = []
        for row in rows:
            score = ScoreRepository._row_to_score(dict(row))
            score.ends = ScoreRepository._load_ends(score.id, cur)
            scores.append(score)

        conn.close()
        return scores

    @staticmethod
    def get_by_competition(competition_id: int) -> List[Score]:
        """All scores for a competition, sorted by total descending (leaderboard order)."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM scores
            WHERE competition_id = ?
            ORDER BY total_score DESC
        """, (competition_id,))
        rows = cur.fetchall()
        scores = []
        for row in rows:
            score = ScoreRepository._row_to_score(dict(row))
            score.ends = ScoreRepository._load_ends(score.id, cur)
            scores.append(score)
        conn.close()
        return scores

    @staticmethod
    def get_personal_best(archer_id: int, round_id: int) -> Optional[Score]:
        """Return the highest-scoring score an archer has shot for a given round."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM scores
            WHERE archer_id = ? AND round_id = ?
            ORDER BY total_score DESC
            LIMIT 1
        """, (archer_id, round_id))
        row = cur.fetchone()
        if not row:
            conn.close()
            return None
        score = ScoreRepository._row_to_score(dict(row))
        score.ends = ScoreRepository._load_ends(score.id, cur)
        conn.close()
        return score

    @staticmethod
    def get_club_best(round_id: int) -> Optional[tuple[Score, Archer]]:
        """
        Return the highest-ever score for a round across all archers,
        together with the Archer who shot it.
        """
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM scores
            WHERE round_id = ?
            ORDER BY total_score DESC
            LIMIT 1
        """, (round_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return None
        score = ScoreRepository._row_to_score(dict(row))
        score.ends = ScoreRepository._load_ends(score.id, cur)
        conn.close()
        archer = ArcherRepository.get_by_id(score.archer_id)
        return score, archer

    @staticmethod
    def approve_staged_score(score_id: int) -> bool:
        """
        Placeholder for the recorder workflow: marks a staged/practice score
        as permanent.  Currently a no-op since is_competition already handles
        the distinction, but kept for future staging-table expansion.
        """
        # Future: move from a staging table into scores
        return ScoreRepository.get_by_id(score_id) is not None

    @staticmethod
    def delete(score_id: int) -> bool:
        conn = get_connection()
        cur = conn.cursor()
        # score_ends cascade-deletes via FK ON DELETE CASCADE
        cur.execute("DELETE FROM scores WHERE id = ?", (score_id,))
        conn.commit()
        deleted = cur.rowcount > 0
        conn.close()
        return deleted

class CompetitionRepository:

    @staticmethod
    def create(name: str, comp_date: date, round_id: int, is_championship: bool = False) -> int:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO competitions (name, date, round_id, is_championship)
            VALUES (?, ?, ?, ?)
        """, (name, comp_date.isoformat(), round_id, int(is_championship)))
        conn.commit()
        comp_id = cur.lastrowid
        conn.close()
        return comp_id

    @staticmethod
    def get_by_id(comp_id: int) -> Optional[dict]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM competitions WHERE id = ?", (comp_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def list_all(championship_only: bool = False) -> List[dict]:
        conn = get_connection()
        cur = conn.cursor()
        if championship_only:
            cur.execute("SELECT * FROM competitions WHERE is_championship = 1 ORDER BY date DESC")
        else:
            cur.execute("SELECT * FROM competitions ORDER BY date DESC")
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_leaderboard(comp_id: int) -> List[tuple[Score, Archer]]:
        """
        Return (Score, Archer) pairs for a competition sorted highest score first.
        """
        scores = ScoreRepository.get_by_competition(comp_id)
        result = []
        for score in scores:
            archer = ArcherRepository.get_by_id(score.archer_id)
            result.append((score, archer))
        return result

    @staticmethod
    def get_championship_results() -> List[dict]:
        """
        Aggregate championship scores: for each archer, sum their scores
        across all championship competitions and rank them.
        Returns list of dicts: {archer, total_score, competitions_shot}.
        """
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT s.archer_id,
                   SUM(s.total_score)   AS total_score,
                   COUNT(s.id)          AS competitions_shot
            FROM scores s
            JOIN competitions c ON s.competition_id = c.id
            WHERE c.is_championship = 1
              AND s.is_competition  = 1
            GROUP BY s.archer_id
            ORDER BY total_score DESC
        """)
        rows = cur.fetchall()
        conn.close()

        results = []
        for row in rows:
            rd = dict(row)
            archer = ArcherRepository.get_by_id(rd['archer_id'])
            results.append({
                'archer': archer,
                'total_score': rd['total_score'],
                'competitions_shot': rd['competitions_shot'],
            })
        return results
