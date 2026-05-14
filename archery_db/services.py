# services.py
"""
Business-logic layer for the Archery Score Recording system.
Wraps raw repository calls with higher-level operations that
correspond to the use-cases described in the database brief.
"""

from datetime import datetime, date
from typing import Optional, List

from repositories import (
    ArcherRepository,
    RoundRepository,
    ScoreRepository,
    CompetitionRepository,
)
from models import Archer, Score
from config import Equipment, Gender, AgeClass


# ---------------------------------------------------------------------------
# Archer services
# ---------------------------------------------------------------------------

def find_archer(archer_id: int) -> Optional[Archer]:
    archer = ArcherRepository.get_by_id(archer_id)
    if not archer:
        print(f"  ✗  No archer found with ID {archer_id}.")
    return archer

def list_all_archers() -> list:
    archers = ArcherRepository.list_all()
    if not archers:
        print("  No archers in the database yet.")
        return []
    print(f"\n{'ID':<6} {'Name':<25} {'Gender':<8} {'Age Class':<12} {'Equipment'}")
    print("-" * 70)
    for a in archers:
        print(f"{a.id:<6} {a.full_name:<25} {a.gender.value:<8} "
              f"{a.age_class.value:<12} {a.default_equipment.value}")
    return archers

# ---------------------------------------------------------------------------
# Round / equivalent-round services
# ---------------------------------------------------------------------------

def list_all_rounds():
    rounds = RoundRepository.list_all()
    if not rounds:
        print("  No rounds defined yet.")
        return []
    print(f"\n{'ID':<6} {'Round Name':<20} {'Arrows':<8} {'Max Score':<12} {'Ranges'}")
    print("-" * 70)
    for r in rounds:
        ranges_summary = ", ".join(
            f"{rd.distance}m×{rd.ends}ends" for rd in r.ranges
        )
        print(f"{r.id:<6} {r.name:<20} {r.total_arrows:<8} {r.possible_score:<12} {ranges_summary}")
    return rounds

def find_round_definition(round_name: str):
    r = RoundRepository.get_by_name(round_name)
    if not r:
        print(f"  ✗  Round '{round_name}' not found.")
        return None
    print(f"\n  Round: {r.name}  (ID {r.id})")
    print(f"  Total arrows: {r.total_arrows}   Max score: {r.possible_score}")
    print(f"\n  {'Range':<8} {'Distance':<12} {'Ends':<8} {'Arrows/End':<12} {'Face (cm)'}")
    print("  " + "-" * 55)
    for i, rd in enumerate(r.ranges, 1):
        print(f"  {i:<8} {rd.distance}m{'':<8} {rd.ends:<8} {rd.arrows_per_end:<12} {rd.face_size}")
    return r

def find_equivalent_round(base_round_name: str, gender: Gender,
                          age_class: AgeClass, equipment: Equipment,
                          as_of: Optional[date] = None):
    base = RoundRepository.get_by_name(base_round_name)
    if not base:
        print(f"  ✗  Base round '{base_round_name}' not found.")
        return None

    equiv = RoundRepository.get_equivalent_round(
        base.id, gender, age_class, equipment, as_of=as_of
    )
    as_of_str = (as_of or date.today()).isoformat()
    category = f"{gender.value} {age_class.value} {equipment.value}"
    if equiv:
        print(f"\n  Category  : {category}")
        print(f"  Base round: {base_round_name}")
        print(f"  Equivalent: {equiv.name}  (as of {as_of_str})")
    else:
        print(f"\n  No equivalent round found for {category} on {base_round_name} "
              f"(as of {as_of_str}).")
        print("  → This category shoots the base round unchanged.")
    return equiv

# ---------------------------------------------------------------------------
# Score services
# ---------------------------------------------------------------------------

def get_archer_scores(
        archer_id: int,
        round_name: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        sort_by: str = "date",
        limit: int = 20,
) -> List[Score]:
    archer = find_archer(archer_id)
    if not archer:
        return []

    round_id = None
    if round_name:
        r = RoundRepository.get_by_name(round_name)
        if r:
            round_id = r.id
        else:
            print(f"  ✗  Round '{round_name}' not found; ignoring filter.")

    scores = ScoreRepository.get_by_archer(
        archer_id,
        limit=limit,
        round_id=round_id,
        from_date=from_date,
        to_date=to_date,
        sort_by=sort_by,
        sort_desc=True,
    )

    if not scores:
        print(f"  No scores found for {archer.full_name}.")
        return []

    print(f"\n  Scores for {archer.full_name}  (showing up to {limit})")
    print(f"  {'ID':<6} {'Date':<22} {'Round':<20} {'Equipment':<18} {'Score':<8} {'Comp?'}")
    print("  " + "-" * 80)
    for s in scores:
        r = RoundRepository.get_by_id(s.round_id)
        round_name_str = r.name if r else f"ID {s.round_id}"
        comp_flag = "Yes" if s.is_competition else "-"
        print(f"  {s.id:<6} {str(s.date_shot)[:19]:<22} {round_name_str:<20} "
              f"{s.equipment.value:<18} {s.total_score:<8} {comp_flag}")
    return scores

def get_personal_best(archer_id: int, round_name: str):
    archer = find_archer(archer_id)
    if not archer:
        return None
    r = RoundRepository.get_by_name(round_name)
    if not r:
        print(f"  ✗  Round '{round_name}' not found.")
        return None
    pb = ScoreRepository.get_personal_best(archer_id, r.id)
    if not pb:
        print(f"  No scores for {archer.full_name} on {round_name}.")
        return None
    print(f"\n  PB for {archer.full_name} on {round_name}: {pb.total_score} "
          f"(shot {str(pb.date_shot)[:10]})")
    return pb

def get_club_best(round_name: str):
    r = RoundRepository.get_by_name(round_name)
    if not r:
        print(f"  ✗  Round '{round_name}' not found.")
        return None
    result = ScoreRepository.get_club_best(r.id)
    if not result:
        print(f"  No scores recorded for {round_name}.")
        return None
    score, archer = result
    print(f"\n  Club best for {round_name}: {score.total_score} "
          f"by {archer.full_name} (shot {str(score.date_shot)[:10]})")
    return result

# ---------------------------------------------------------------------------
# Competition services
# ---------------------------------------------------------------------------

def list_competitions(championship_only: bool = False):
    comps = CompetitionRepository.list_all(championship_only=championship_only)
    if not comps:
        print("  No competitions found.")
        return []
    label = "Championship competitions" if championship_only else "All competitions"
    print(f"\n  {label}:")
    print(f"  {'ID':<6} {'Date':<12} {'Championship':<14} {'Name'}")
    print("  " + "-" * 60)
    for c in comps:
        champ = "Yes" if c.get("is_championship") else "-"
        print(f"  {c['id']:<6} {c['date']:<12} {champ:<14} {c['name']}")
    return comps

def show_competition_leaderboard(comp_id: int):
    comp = CompetitionRepository.get_by_id(comp_id)
    if not comp:
        print(f"  ✗  Competition {comp_id} not found.")
        return
    print(f"\n  Leaderboard — {comp['name']}  ({comp['date']})")
    print(f"  {'Rank':<6} {'Name':<25} {'Equipment':<18} {'Score'}")
    print("  " + "-" * 60)
    results = CompetitionRepository.get_leaderboard(comp_id)
    for rank, (score, archer) in enumerate(results, 1):
        print(f"  {rank:<6} {archer.full_name:<25} {score.equipment.value:<18} {score.total_score}")

def show_championship_results():
    results = CompetitionRepository.get_championship_results()
    if not results:
        print("  No championship scores found.")
        return
    print(f"\n  Club Championship Results:")
    print(f"  {'Rank':<6} {'Name':<25} {'Comps Shot':<12} {'Total Score'}")
    print("  " + "-" * 55)
    for rank, row in enumerate(results, 1):
        print(f"  {rank:<6} {row['archer'].full_name:<25} "
              f"{row['competitions_shot']:<12} {row['total_score']}")
