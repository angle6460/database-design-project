#!/usr/bin/env python3
# data_entry.py
"""
Archery Score Recording System — Data Entry Module
---------------------------------------------------
Provides two entry points:

  Archer mode  (menu_archer_entry)
    - Stage a new practice or competition score (arrow-by-arrow, per end)
    - View pending staged scores

  Recorder mode  (menu_recorder_entry)
    - Add a new archer
    - Add a new round definition
    - Add a new competition
    - Approve / reject staged scores
    - Assign a score to a competition
    - Mark a competition as part of the club championship

Designed to be imported from main.py and called from the main menu.
Can also be run standalone: python data_entry.py
"""

import sys
import os

# ---------------------------------------------------------------------------
# Path setup so this module works when run from the archery_db/ directory
# or from the project root.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ARCHERY_DB = os.path.join(_HERE, "archery_db")
if _ARCHERY_DB not in sys.path:
    sys.path.insert(0, _ARCHERY_DB)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from datetime import datetime, date
from typing import Optional, List

from database import get_connection, init_db
from repositories import ArcherRepository, RoundRepository, ScoreRepository, CompetitionRepository
from models import Archer, Round, RangeDefinition, Score, End
from config import Gender, AgeClass, Equipment


# ===========================================================================
# Shared UI helpers
# ===========================================================================

def _hr(char="─", width=62):
    print("\n" + char * width)


def _banner(title: str):
    _hr("═")
    print(f"  {title}")
    _hr("═")


def _prompt(label: str, default: str = "", required: bool = False) -> str:
    """Prompt the user for text input. Supports optional default value."""
    suffix = f" [{default}]" if default else (" (required)" if required else "")
    while True:
        raw = input(f"  {label}{suffix}: ").strip()
        val = raw if raw else default
        if required and not val:
            print("  ✗  This field is required.")
        else:
            return val


def _prompt_int(label: str, default: int = None, min_val: int = None, max_val: int = None) -> int:
    """Prompt for an integer with optional range validation."""
    default_str = str(default) if default is not None else ""
    while True:
        raw = _prompt(label, default=default_str)
        if not raw:
            if default is not None:
                return default
            print("  ✗  A number is required.")
            continue
        if not raw.lstrip("-").isdigit():
            print("  ✗  Please enter a whole number.")
            continue
        val = int(raw)
        if min_val is not None and val < min_val:
            print(f"  ✗  Minimum is {min_val}.")
            continue
        if max_val is not None and val > max_val:
            print(f"  ✗  Maximum is {max_val}.")
            continue
        return val


def _prompt_date(label: str, default: date = None) -> date:
    """Prompt for a date in YYYY-MM-DD format."""
    default_str = default.isoformat() if default else ""
    while True:
        raw = _prompt(label + " (YYYY-MM-DD)", default=default_str)
        if not raw:
            if default:
                return default
            print("  ✗  Date is required.")
            continue
        try:
            return date.fromisoformat(raw)
        except ValueError:
            print("  ✗  Use YYYY-MM-DD format, e.g. 2025-06-01.")


def _prompt_datetime(label: str, default: datetime = None) -> datetime:
    """Prompt for date+time; time defaults to 00:00 if omitted."""
    default_str = default.strftime("%Y-%m-%d %H:%M") if default else ""
    while True:
        raw = _prompt(label + " (YYYY-MM-DD HH:MM, time optional)", default=default_str)
        if not raw:
            if default:
                return default
            print("  ✗  Date/time is required.")
            continue
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        print("  ✗  Use format YYYY-MM-DD or YYYY-MM-DD HH:MM.")


def _pick_enum(enum_cls, label: str, allow_skip: bool = False):
    """
    Numbered picker for any Enum.  Returns chosen member, or None if skipped.
    """
    members = list(enum_cls)
    print(f"\n  {label}:")
    for i, m in enumerate(members, 1):
        print(f"    {i:>2}.  {m.value}")
    if allow_skip:
        print(f"    {'0':>2}.  (skip / use default)")
    while True:
        raw = input("  Choice: ").strip()
        if allow_skip and raw == "0":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(members):
            return members[int(raw) - 1]
        print("  Invalid — enter a number from the list.")


def _confirm(prompt: str = "Confirm? (y/n)") -> bool:
    return input(f"  {prompt} ").strip().lower() in ["y", "yes", 'confirmed']


def _pick_round(label: str = "Round") -> Optional[Round]:
    """Let the user select a round by name or ID."""
    rounds = RoundRepository.list_all()
    if not rounds:
        print("  ✗  No rounds in the database. Please add rounds first.")
        return None
    print(f"\n  Available rounds:")
    for r in rounds:
        print(f"    {r.id:>4}  {r.name}")
    while True:
        raw = _prompt(f"{label} (name or ID)")
        if not raw:
            return None
        # Try by ID first
        if raw.isdigit():
            match = next((r for r in rounds if r.id == int(raw)), None)
        else:
            match = next((r for r in rounds if r.name.lower() == raw.lower()), None)
        if match:
            return match
        print(f"  ✗  Round '{raw}' not found.")


def _pick_archer(label: str = "Archer") -> Optional[Archer]:
    """Let the user select an archer by name or ID."""
    archers = ArcherRepository.list_all()
    if not archers:
        print("  ✗  No archers in the database.")
        return None
    print(f"\n  Archers (first 30 shown):")
    for a in archers[:30]:
        print(f"    {a.id:>4}  {a.full_name:<25}  {a.age_class.value}  {a.default_equipment.value}")
    if len(archers) > 30:
        print(f"    ... and {len(archers) - 30} more. Enter ID or full name to select.")
    while True:
        raw = _prompt(f"{label} (ID or full name)")
        if not raw:
            return None
        if raw.isdigit():
            match = ArcherRepository.get_by_id(int(raw))
        else:
            parts = raw.strip().split()
            match = next(
                (a for a in archers if a.full_name.lower() == raw.lower()),
                None,
            )
        if match:
            return match
        print(f"  ✗  Archer '{raw}' not found.")


# ===========================================================================
# STAGED SCORES  (lightweight SQLite table for archer-entered scores)
# ===========================================================================

def _ensure_staged_scores_table():
    """Create the staged_scores and staged_ends tables if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS staged_scores (
            id            INTEGER PRIMARY KEY,
            archer_id     INTEGER NOT NULL,
            round_id      INTEGER NOT NULL,
            equipment     TEXT    NOT NULL,
            date_shot     DATETIME NOT NULL,
            is_competition BOOLEAN DEFAULT 0,
            notes         TEXT,
            status        TEXT DEFAULT 'pending',   -- 'pending' | 'approved' | 'rejected'
            staged_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(archer_id) REFERENCES archers(id),
            FOREIGN KEY(round_id)  REFERENCES rounds(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS staged_ends (
            id           INTEGER PRIMARY KEY,
            staged_id    INTEGER NOT NULL,
            range_number INTEGER NOT NULL,
            end_number   INTEGER NOT NULL,
            arrow1       INTEGER,
            arrow2       INTEGER,
            arrow3       INTEGER,
            arrow4       INTEGER,
            arrow5       INTEGER,
            arrow6       INTEGER,
            FOREIGN KEY(staged_id) REFERENCES staged_scores(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


def _save_staged_score(archer_id: int, round_id: int, equipment: Equipment,
                        date_shot: datetime, ends: List[End],
                        is_competition: bool = False, notes: str = "") -> int:
    _ensure_staged_scores_table()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO staged_scores (archer_id, round_id, equipment, date_shot, is_competition, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (archer_id, round_id, equipment.value, date_shot.isoformat(),
          int(is_competition), notes))
    staged_id = cur.lastrowid

    for end in ends:
        arrows = end.arrows + [None] * (6 - len(end.arrows))
        cur.execute("""
            INSERT INTO staged_ends (staged_id, range_number, end_number,
                                     arrow1, arrow2, arrow3, arrow4, arrow5, arrow6)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (staged_id, end.range_number, end.end_number, *arrows))

    conn.commit()
    conn.close()
    return staged_id


def _list_staged_scores(status: str = "pending") -> List[dict]:
    _ensure_staged_scores_table()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ss.*, a.first_name || ' ' || a.last_name AS archer_name, r.name AS round_name
        FROM staged_scores ss
        JOIN archers a ON a.id = ss.archer_id
        JOIN rounds  r ON r.id = ss.round_id
        WHERE ss.status = ?
        ORDER BY ss.staged_at DESC
    """, (status,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _get_staged_ends(staged_id: int) -> List[End]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM staged_ends WHERE staged_id = ?
        ORDER BY range_number, end_number
    """, (staged_id,))
    ends = []
    for r in cur.fetchall():
        rd = dict(r)
        arrows = [rd[f"arrow{i}"] for i in range(1, 7) if rd.get(f"arrow{i}") is not None]
        ends.append(End(end_number=rd["end_number"], range_number=rd["range_number"], arrows=arrows))
    conn.close()
    return ends


def _approve_staged(staged_id: int) -> bool:
    """
    Move a staged score into the permanent scores table and mark it approved.
    Validates that equipment on the score matches the archer's default equipment.
    """
    _ensure_staged_scores_table()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM staged_scores WHERE id = ?", (staged_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        print(f"  ✗  Staged score {staged_id} not found.")
        return False

    data = dict(row)
    archer = ArcherRepository.get_by_id(data["archer_id"])
    round_obj = RoundRepository.get_by_id(data["round_id"])
    equipment = Equipment(data["equipment"])

    # Equipment check
    if equipment != archer.default_equipment:
        print(f"  ⚠️   Equipment mismatch: staged={equipment.value}, "
              f"archer default={archer.default_equipment.value}")
        if not _confirm("Approve anyway?"):
            return False

    ends = _get_staged_ends(staged_id)
    total_score = sum(sum(e.arrows) for e in ends)

    score = Score(
        archer_id=data["archer_id"],
        round_id=data["round_id"],
        equipment=equipment,
        date_shot=datetime.fromisoformat(data["date_shot"]),
        is_competition=bool(data["is_competition"]),
        total_score=total_score,
        ends=ends,
        notes=data.get("notes") or "",
    )
    ScoreRepository.save(score)

    # Mark staged record as approved
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE staged_scores SET status='approved' WHERE id=?", (staged_id,))
    conn.commit()
    conn.close()
    print(f"  ✅  Score approved and saved (total: {total_score}).")
    return True


def _reject_staged(staged_id: int, reason: str = ""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE staged_scores SET status='rejected', notes=? WHERE id=?",
                (reason or "Rejected by recorder", staged_id))
    conn.commit()
    conn.close()
    print(f"  ✅  Staged score {staged_id} marked as rejected.")


# ===========================================================================
# ARROW INPUT  — the core data-entry workflow for a score
# ===========================================================================

def _enter_arrows_for_round(round_obj: Round, equipment: Equipment) -> List[End]:
    """
    Walk the user through entering arrow scores end-by-end for a round.
    Returns the complete list of End objects.
    Arrow scores must be 0–10, sorted highest→lowest (rules requirement).
    Minimum 6 complete ends per range must be recorded.
    """
    ends: List[End] = []
    arrows_per_end = 6  # always 6 per brief

    print(f"\n  Round: {round_obj.name}  |  Equipment: {equipment.value}")
    print(f"  Enter {arrows_per_end} arrow scores per end (0–10), space-separated.")
    print(f"  Arrows will be re-sorted highest→lowest automatically.\n")

    for range_idx, range_def in enumerate(round_obj.ranges, start=1):
        print(f"  ── Range {range_idx}: {range_def.distance}m, "
              f"{range_def.ends} ends, {range_def.face_size}cm face ──")

        for end_num in range(1, range_def.ends + 1):
            while True:
                raw = input(f"    Range {range_idx} / End {end_num} "
                            f"({arrows_per_end} arrows): ").strip()
                parts = raw.split()
                if len(parts) != arrows_per_end:
                    print(f"    ✗  Please enter exactly {arrows_per_end} scores.")
                    continue
                try:
                    scores_in = [int(p) for p in parts]
                except ValueError:
                    print("    ✗  Use whole numbers only.")
                    continue
                if any(s < 0 or s > 10 for s in scores_in):
                    print("    ✗  Each score must be 0–10.")
                    continue
                # Sort highest to lowest per rules
                arrows = sorted(scores_in, reverse=True)
                end_total = sum(arrows)
                print(f"    → {arrows}  (end total: {end_total})")
                ends.append(End(
                    end_number=end_num,
                    range_number=range_idx,
                    arrows=arrows,
                ))
                break

        range_total = sum(sum(e.arrows) for e in ends if e.range_number == range_idx)
        print(f"  Range {range_idx} total: {range_total}\n")

    grand_total = sum(sum(e.arrows) for e in ends)
    print(f"  ── Grand total: {grand_total} / {round_obj.possible_score} ──")
    return ends


# ===========================================================================
# ARCHER ENTRY MENU
# ===========================================================================

def menu_stage_score():
    """Archer workflow: enter a score and save it to the staging table."""
    _banner("STAGE A SCORE  (archer self-entry)")

    archer = _pick_archer("Your archer record")
    if not archer:
        return

    print(f"\n  Archer: {archer.full_name}  |  Default equipment: {archer.default_equipment.value}")

    round_obj = _pick_round("Round shot")
    if not round_obj:
        return

    # Equipment — default to archer's default, but allow override
    print(f"\n  Equipment (press Enter to use default: {archer.default_equipment.value}):")
    equipment = _pick_enum(Equipment, "Equipment", allow_skip=True)
    if equipment is None:
        equipment = archer.default_equipment

    date_shot = _prompt_datetime("Date/time shot", default=datetime.now())

    is_comp_str = _prompt("Is this a competition score? (y/n)", default="n")
    is_competition = is_comp_str.lower() == "y"

    notes = _prompt("Notes (optional)")

    print()
    ends = _enter_arrows_for_round(round_obj, equipment)

    print("\n  Review:")
    print(f"    Archer    : {archer.full_name}")
    print(f"    Round     : {round_obj.name}")
    print(f"    Equipment : {equipment.value}")
    print(f"    Date shot : {date_shot.strftime('%Y-%m-%d %H:%M')}")
    print(f"    Competition: {'Yes' if is_competition else 'No'}")
    print(f"    Total     : {sum(sum(e.arrows) for e in ends)}")
    if notes:
        print(f"    Notes     : {notes}")

    if _confirm("\n  Submit this score for recorder approval?"):
        sid = _save_staged_score(
            archer_id=archer.id,
            round_id=round_obj.id,
            equipment=equipment,
            date_shot=date_shot,
            ends=ends,
            is_competition=is_competition,
            notes=notes,
        )
        print(f"\n  ✅  Score staged successfully (staged ID: {sid}).")
        print("  The club recorder will review and approve it.")
    else:
        print("  Cancelled — score not saved.")


def menu_view_my_staged_scores():
    """Archer workflow: view their own pending staged scores."""
    _banner("MY STAGED SCORES")
    archer = _pick_archer("Your archer record")
    if not archer:
        return
    _ensure_staged_scores_table()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ss.id, ss.date_shot, ss.equipment, ss.status, ss.notes,
               r.name AS round_name
        FROM staged_scores ss
        JOIN rounds r ON r.id = ss.round_id
        WHERE ss.archer_id = ?
        ORDER BY ss.staged_at DESC
        LIMIT 30
    """, (archer.id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    if not rows:
        print(f"\n  No staged scores found for {archer.full_name}.")
        return

    print(f"\n  Staged scores for {archer.full_name}:")
    print(f"  {'ID':<6} {'Date Shot':<20} {'Round':<20} {'Equipment':<18} {'Status'}")
    print("  " + "-" * 75)
    for r in rows:
        print(f"  {r['id']:<6} {str(r['date_shot'])[:19]:<20} {r['round_name']:<20} "
              f"{r['equipment']:<18} {r['status']}")


def menu_archer_entry():
    """Top-level archer data-entry sub-menu."""
    while True:
        _hr()
        print("  ARCHER SELF-ENTRY")
        print("    a  Stage a new score")
        print("    b  View my staged scores")
        print("    0  Back")
        choice = input("  Choice: ").strip().lower()
        if choice == "0":
            break
        elif choice == "a":
            menu_stage_score()
        elif choice == "b":
            menu_view_my_staged_scores()
        else:
            print("  Unknown option.")


# ===========================================================================
# RECORDER ENTRY MENU
# ===========================================================================

def recorder_add_archer():
    """Recorder: create a new archer record."""
    _banner("ADD NEW ARCHER")

    first_name = _prompt("First name", required=True)
    last_name  = _prompt("Last name",  required=True)
    gender     = _pick_enum(Gender,    "Gender")
    age_class  = _pick_enum(AgeClass,  "Age class")
    equipment  = _pick_enum(Equipment, "Default equipment")
    dob        = _prompt_date("Date of birth", default=None)

    archer = Archer(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        age_class=age_class,
        default_equipment=equipment,
        date_of_birth=dob,
    )

    print("\n  Review:")
    print(f"    Name      : {archer.full_name}")
    print(f"    Gender    : {gender.value}")
    print(f"    Age class : {age_class.value}")
    print(f"    Equipment : {equipment.value}")
    print(f"    DOB       : {dob}")

    if _confirm("\n  Save this archer?"):
        archer_id = ArcherRepository.create(archer)
        print(f"  ✅  Archer saved (ID: {archer_id}).")
    else:
        print("  Cancelled.")


def recorder_add_round():
    """Recorder: define a new round with its ranges."""
    _banner("ADD NEW ROUND DEFINITION")

    name = _prompt("Round name (e.g. WA70/1440)", required=True)
    existing = RoundRepository.get_by_name(name)
    if existing:
        print(f"  ✗  A round named '{name}' already exists (ID {existing.id}).")
        return

    num_ranges = _prompt_int("Number of ranges", default=2, min_val=1, max_val=10)
    ranges: List[RangeDefinition] = []

    for i in range(1, num_ranges + 1):
        print(f"\n  Range {i}:")
        distance      = _prompt_int(f"    Distance (m)", min_val=10, max_val=120)
        ends          = _prompt_int(f"    Ends (5 or 6)", default=6, min_val=5, max_val=6)
        face_raw      = _prompt_int(f"    Face size cm (80 or 122)", default=80)
        face_size     = 122 if face_raw >= 100 else 80
        ranges.append(RangeDefinition(distance=distance, ends=ends, face_size=face_size))

    total_arrows   = sum(r.ends * 6 for r in ranges)
    possible_score = total_arrows * 10

    valid_from_str = _prompt("Valid from date YYYY-MM-DD (optional)")
    valid_from = date.fromisoformat(valid_from_str) if valid_from_str else None

    round_obj = Round(
        name=name,
        total_arrows=total_arrows,
        possible_score=possible_score,
        ranges=ranges,
        valid_from=valid_from,
    )

    print("\n  Review:")
    print(f"    Name          : {name}")
    print(f"    Total arrows  : {total_arrows}")
    print(f"    Possible score: {possible_score}")
    for i, r in enumerate(ranges, 1):
        print(f"    Range {i}       : {r.distance}m  ×  {r.ends} ends  |  {r.face_size}cm face")

    if _confirm("\n  Save this round?"):
        rid = RoundRepository.create(round_obj)
        print(f"  ✅  Round saved (ID: {rid}).")
    else:
        print("  Cancelled.")


def recorder_add_competition():
    """Recorder: create a new competition."""
    _banner("ADD NEW COMPETITION")

    name = _prompt("Competition name", required=True)
    comp_date = _prompt_date("Competition date")
    round_obj = _pick_round("Round for this competition")
    if not round_obj:
        return

    is_champ = _prompt("Is this part of the club championship? (y/n)", default="n").lower() == "y"

    print("\n  Review:")
    print(f"    Name         : {name}")
    print(f"    Date         : {comp_date}")
    print(f"    Round        : {round_obj.name}")
    print(f"    Championship : {'Yes' if is_champ else 'No'}")

    if _confirm("\n  Save this competition?"):
        comp_id = CompetitionRepository.create(name, comp_date, round_obj.id, is_championship=is_champ)
        print(f"  ✅  Competition saved (ID: {comp_id}).")
    else:
        print("  Cancelled.")


def recorder_enter_score_direct():
    """
    Recorder: directly enter a complete score (bypasses staging).
    Used for paper scorecards entered by the recorder.
    """
    _banner("DIRECT SCORE ENTRY  (recorder)")

    archer = _pick_archer("Archer")
    if not archer:
        return

    round_obj = _pick_round("Round shot")
    if not round_obj:
        return

    equipment = _pick_enum(Equipment, "Equipment", allow_skip=True)
    if equipment is None:
        equipment = archer.default_equipment

    date_shot = _prompt_datetime("Date/time shot", default=datetime.now())

    is_comp_str = _prompt("Is this a competition score? (y/n)", default="n")
    is_competition = is_comp_str.lower() == "y"

    comp_id = None
    if is_competition:
        # Let the recorder optionally link to an existing competition
        comps = CompetitionRepository.list_all()
        if comps:
            print("\n  Available competitions (most recent first):")
            for c in comps[:15]:
                print(f"    {c['id']:>4}  {c['date']}  {c['name']}")
            raw_cid = _prompt("Competition ID to link (Enter to skip)")
            if raw_cid.isdigit():
                comp_id = int(raw_cid)

    notes = _prompt("Notes (optional)")

    print()
    ends = _enter_arrows_for_round(round_obj, equipment)
    total_score = sum(sum(e.arrows) for e in ends)

    print("\n  Review:")
    print(f"    Archer     : {archer.full_name}")
    print(f"    Round      : {round_obj.name}")
    print(f"    Equipment  : {equipment.value}")
    print(f"    Date shot  : {date_shot.strftime('%Y-%m-%d %H:%M')}")
    print(f"    Competition: {'Yes (ID ' + str(comp_id) + ')' if comp_id else ('Yes' if is_competition else 'No')}")
    print(f"    Total      : {total_score} / {round_obj.possible_score}")

    if _confirm("\n  Save this score permanently?"):
        score = Score(
            archer_id=archer.id,
            round_id=round_obj.id,
            equipment=equipment,
            date_shot=date_shot,
            is_competition=is_competition,
            competition_id=comp_id,
            total_score=total_score,
            ends=ends,
            notes=notes,
        )
        ScoreRepository.save(score)
        print(f"  ✅  Score saved (ID: {score.id}).")
    else:
        print("  Cancelled.")


def recorder_approve_staged():
    """Recorder: review and approve or reject pending staged scores."""
    _banner("APPROVE / REJECT STAGED SCORES")

    pending = _list_staged_scores(status="pending")
    if not pending:
        print("\n  No pending staged scores.")
        return

    print(f"\n  {'ID':<6} {'Archer':<22} {'Round':<20} {'Equipment':<18} "
          f"{'Date Shot':<20} {'Comp?'}")
    print("  " + "-" * 90)
    for s in pending:
        comp = "Yes" if s.get("is_competition") else "-"
        print(f"  {s['id']:<6} {s['archer_name']:<22} {s['round_name']:<20} "
              f"{s['equipment']:<18} {str(s['date_shot'])[:19]:<20} {comp}")

    print()
    while True:
        raw = _prompt("Enter staged ID to review (or blank to finish)")
        if not raw:
            break
        if not raw.isdigit():
            print("  ✗  Enter a number.")
            continue

        staged_id = int(raw)
        match = next((s for s in pending if s["id"] == staged_id), None)
        if not match:
            print(f"  ✗  Staged score {staged_id} not in pending list.")
            continue

        # Show detail
        ends = _get_staged_ends(staged_id)
        total = sum(sum(e.arrows) for e in ends)
        print(f"\n  Staged score {staged_id}:")
        print(f"    Archer    : {match['archer_name']}")
        print(f"    Round     : {match['round_name']}")
        print(f"    Equipment : {match['equipment']}")
        print(f"    Date shot : {match['date_shot']}")
        print(f"    Total     : {total}")
        print(f"    Notes     : {match.get('notes') or '-'}")
        print(f"\n  End breakdown:")
        for e in ends:
            print(f"    Range {e.range_number} End {e.end_number}: "
                  f"{e.arrows}  = {sum(e.arrows)}")

        action = _prompt("Action: (a)pprove / (r)eject / (s)kip", default="s").lower()
        if action == "a":
            _approve_staged(staged_id)
        elif action == "r":
            reason = _prompt("Rejection reason (optional)")
            _reject_staged(staged_id, reason)
        else:
            print("  Skipped.")


def recorder_assign_score_to_competition():
    """Recorder: link an existing score to a competition."""
    _banner("ASSIGN SCORE TO COMPETITION")

    comps = CompetitionRepository.list_all()
    if not comps:
        print("  ✗  No competitions found.")
        return

    print("\n  Competitions:")
    for c in comps[:20]:
        champ = " [CHAMP]" if c.get("is_championship") else ""
        print(f"    {c['id']:>4}  {c['date']}  {c['name']}{champ}")

    comp_id = _prompt_int("Competition ID", min_val=1)
    comp = CompetitionRepository.get_by_id(comp_id)
    if not comp:
        print(f"  ✗  Competition {comp_id} not found.")
        return

    score_id = _prompt_int("Score ID to assign", min_val=1)
    score = ScoreRepository.get_by_id(score_id)
    if not score:
        print(f"  ✗  Score {score_id} not found.")
        return

    archer = ArcherRepository.get_by_id(score.archer_id)
    print(f"\n  Linking score {score_id} (archer: {archer.full_name if archer else '?'}, "
          f"total: {score.total_score}) → competition '{comp['name']}'")

    if _confirm("Confirm?"):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE scores
            SET competition_id = ?, is_competition = 1
            WHERE id = ?
        """, (comp_id, score_id))
        conn.commit()
        conn.close()
        print("  ✅  Score linked to competition.")
    else:
        print("  Cancelled.")


def recorder_toggle_championship():
    """Recorder: mark or unmark a competition as part of the club championship."""
    _banner("CHAMPIONSHIP FLAG  (toggle)")

    comps = CompetitionRepository.list_all()
    if not comps:
        print("  ✗  No competitions found.")
        return

    print(f"\n  {'ID':<6} {'Championship':<14} {'Date':<12} {'Name'}")
    print("  " + "-" * 60)
    for c in comps:
        champ = "✓ Yes" if c.get("is_championship") else "  No"
        print(f"  {c['id']:<6} {champ:<14} {c['date']:<12} {c['name']}")

    comp_id = _prompt_int("Competition ID to toggle", min_val=1)
    comp = CompetitionRepository.get_by_id(comp_id)
    if not comp:
        print(f"  ✗  Competition {comp_id} not found.")
        return

    current = bool(comp.get("is_championship"))
    new_val = not current
    print(f"\n  '{comp['name']}': championship = {current} → {new_val}")

    if _confirm("Confirm toggle?"):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE competitions SET is_championship = ? WHERE id = ?",
                    (int(new_val), comp_id))
        conn.commit()
        conn.close()
        print(f"  ✅  Championship flag set to {new_val}.")
    else:
        print("  Cancelled.")


def recorder_update_archer():
    """Recorder: update an existing archer's details."""
    _banner("UPDATE ARCHER RECORD")

    archer = _pick_archer("Archer to update")
    if not archer:
        return

    print(f"\n  Current details for {archer.full_name}:")
    print(f"    Gender    : {archer.gender.value}")
    print(f"    Age class : {archer.age_class.value}")
    print(f"    Equipment : {archer.default_equipment.value}")
    print(f"    DOB       : {archer.date_of_birth}")
    print("\n  Press Enter to keep the current value for each field.\n")

    fn  = _prompt("First name", default=archer.first_name)
    ln  = _prompt("Last name",  default=archer.last_name)

    print(f"\n  Gender (current: {archer.gender.value}, Enter to keep):")
    g_choice = input("  Change? (y/n): ").strip().lower()
    gender = _pick_enum(Gender, "Gender") if g_choice == "y" else archer.gender

    print(f"\n  Age class (current: {archer.age_class.value}, Enter to keep):")
    ac_choice = input("  Change? (y/n): ").strip().lower()
    age_class = _pick_enum(AgeClass, "Age class") if ac_choice == "y" else archer.age_class

    print(f"\n  Equipment (current: {archer.default_equipment.value}, Enter to keep):")
    eq_choice = input("  Change? (y/n): ").strip().lower()
    equipment = _pick_enum(Equipment, "Equipment") if eq_choice == "y" else archer.default_equipment

    dob_str = _prompt("Date of birth (YYYY-MM-DD)",
                      default=str(archer.date_of_birth) if archer.date_of_birth else "")
    dob = date.fromisoformat(dob_str) if dob_str else archer.date_of_birth

    archer.first_name        = fn
    archer.last_name         = ln
    archer.gender            = gender
    archer.age_class         = age_class
    archer.default_equipment = equipment
    archer.date_of_birth     = dob

    if _confirm(f"\n  Save changes for {archer.full_name}?"):
        ArcherRepository.update(archer)
        print("  ✅  Archer updated.")
    else:
        print("  Cancelled.")


def menu_recorder_entry():
    """Top-level recorder data-entry sub-menu."""
    while True:
        _hr()
        print("  RECORDER DATA ENTRY")
        print("    a  Add new archer")
        print("    b  Update archer record")
        print("    c  Add new round definition")
        print("    d  Add new competition")
        print("    e  Direct score entry (paper scorecard)")
        print("    f  Approve / reject staged scores")
        print("    g  Assign score to a competition")
        print("    h  Toggle competition championship flag")
        print("    0  Back")
        choice = input("  Choice: ").strip().lower()

        if   choice == "0": break
        elif choice == "a": recorder_add_archer()
        elif choice == "b": recorder_update_archer()
        elif choice == "c": recorder_add_round()
        elif choice == "d": recorder_add_competition()
        elif choice == "e": recorder_enter_score_direct()
        elif choice == "f": recorder_approve_staged()
        elif choice == "g": recorder_assign_score_to_competition()
        elif choice == "h": recorder_toggle_championship()
        else: print("  Unknown option.")


# ===========================================================================
# Standalone entry point
# ===========================================================================

def main():
    print("\n" + "=" * 62)
    print("  🏹  Archery Score Recording — Data Entry")
    print("=" * 62)
    init_db()
    _ensure_staged_scores_table()

    while True:
        _hr("═")
        print("  DATA ENTRY MENU")
        print("  1  Archer self-entry  (stage scores on handheld device)")
        print("  2  Recorder entry     (manage archers, rounds, competitions)")
        print("  0  Exit")
        choice = input("  Choice: ").strip()

        if   choice == "0": print("\n  Returning! 🏹\n"); break
        elif choice == "1": menu_archer_entry()
        elif choice == "2": menu_recorder_entry()
        else: print("  Unknown option.")


if __name__ == "__main__":
    main()