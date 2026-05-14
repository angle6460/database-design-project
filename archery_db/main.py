#!/usr/bin/env python3
# main.py
"""
Archery Score Recording System — Interactive CLI
-------------------------------------------------
Run with:  python main.py

Menu structure
  1  Seed database (rounds + archers + scores + competitions)
  2  Archer lookup
       2a  List all archers
       2b  View an archer's scores  (filterable by round, date range, sort)
       2c  Personal best for an archer on a round
  3  Round lookup
       3a  List all rounds with their range definitions
       3b  Find round definition by name
       3c  Find equivalent round for a category
  4  Competition lookup
       4a  List all competitions
       4b  Competition leaderboard
       4c  Club championship results
  5  Club records
       5a  Club best for a round
  0  Exit
"""

from database import init_db
from data_generator import ArcheryDataGenerator
from config import Gender, AgeClass, Equipment
from datetime import datetime
import services


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hr():
    print("\n" + "─" * 60)


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"  {label}{suffix}: ").strip()
    return raw if raw else default


def _pick_enum(enum_cls, label: str):
    """Present a numbered list of enum values; return the chosen member."""
    members = list(enum_cls)
    print(f"\n  {label}:")
    for i, m in enumerate(members, 1):
        print(f"    {i}. {m.value}")
    while True:
        raw = input("  Choice: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(members):
            return members[int(raw) - 1]
        print("  Invalid — enter a number from the list.")


# ---------------------------------------------------------------------------
# Sub-menus
# ---------------------------------------------------------------------------

def menu_seed():
    _hr()
    print("  SEED DATABASE")
    print("  This will populate the DB with rounds, archers, practice scores")
    print("  and competitions. Existing data is NOT wiped first.")
    num_archers  = int(_prompt("Number of archers to generate", "50"))
    scores_each  = int(_prompt("Practice scores per archer", "10"))
    num_comps    = int(_prompt("Number of competitions", "8"))
    print()
    gen = ArcheryDataGenerator()
    gen.seed_all(
        num_archers=num_archers,
        scores_per_archer=scores_each,
        num_competitions=num_comps,
    )


def menu_archer():
    while True:
        _hr()
        print("  ARCHER LOOKUP")
        print("    a  List all archers")
        print("    b  View archer scores")
        print("    c  Personal best on a round")
        print("    0  Back")
        choice = _prompt("Choice").lower()

        if choice == "0":
            break

        elif choice == "a":
            services.list_all_archers()

        elif choice == "b":
            archer_id = int(_prompt("Archer ID"))
            round_name = _prompt("Filter by round name (leave blank for all)")
            from_str   = _prompt("From date YYYY-MM-DD (blank = no limit)")
            to_str     = _prompt("To date   YYYY-MM-DD (blank = no limit)")
            sort_by    = _prompt("Sort by: 'date' or 'score'", "date")
            limit      = int(_prompt("Max results", "20"))

            from_dt = datetime.strptime(from_str, "%Y-%m-%d") if from_str else None
            to_dt   = datetime.strptime(to_str,   "%Y-%m-%d") if to_str   else None

            services.get_archer_scores(
                archer_id=archer_id,
                round_name=round_name or None,
                from_date=from_dt,
                to_date=to_dt,
                sort_by=sort_by,
                limit=limit,
            )

        elif choice == "c":
            archer_id  = int(_prompt("Archer ID"))
            round_name = _prompt("Round name (e.g. WA70/1440)")
            services.get_personal_best(archer_id, round_name)

        else:
            print("  Unknown option.")


def menu_rounds():
    while True:
        _hr()
        print("  ROUND LOOKUP")
        print("    a  List all rounds")
        print("    b  Round definition by name")
        print("    c  Find equivalent round for a category")
        print("    0  Back")
        choice = _prompt("Choice").lower()

        if choice == "0":
            break

        elif choice == "a":
            services.list_all_rounds()

        elif choice == "b":
            name = _prompt("Round name (e.g. WA70/1440)")
            services.find_round_definition(name)

        elif choice == "c":
            base_name  = _prompt("Base round name (e.g. WA90/1440)")
            gender     = _pick_enum(Gender,   "Gender")
            age_class  = _pick_enum(AgeClass, "Age class")
            equipment  = _pick_enum(Equipment,"Equipment")
            as_of_str  = _prompt("As-of date YYYY-MM-DD (blank = today)")
            as_of = (
                datetime.strptime(as_of_str, "%Y-%m-%d").date()
                if as_of_str else None
            )
            services.find_equivalent_round(base_name, gender, age_class, equipment, as_of)

        else:
            print("  Unknown option.")


def menu_competitions():
    while True:
        _hr()
        print("  COMPETITION LOOKUP")
        print("    a  List all competitions")
        print("    b  Competition leaderboard")
        print("    c  Club championship results")
        print("    0  Back")
        choice = _prompt("Choice").lower()

        if choice == "0":
            break

        elif choice == "a":
            champ_only = _prompt("Championship only? (y/n)", "n").lower() == "y"
            services.list_competitions(championship_only=champ_only)

        elif choice == "b":
            comp_id = int(_prompt("Competition ID"))
            services.show_competition_leaderboard(comp_id)

        elif choice == "c":
            services.show_championship_results()

        else:
            print("  Unknown option.")


def menu_club_records():
    _hr()
    print("  CLUB RECORDS")
    round_name = _prompt("Round name (e.g. WA70/1440)")
    services.get_club_best(round_name)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 60)
    print("  🏹  Archery Score Recording System")
    print("=" * 60)
    init_db()

    while True:
        _hr()
        print("  MAIN MENU")
        print("  1  Seed database")
        print("  2  Archer lookup")
        print("  3  Round lookup")
        print("  4  Competition lookup")
        print("  5  Club records")
        print("  0  Exit")
        choice = _prompt("Choice")

        if   choice == "0": print("\n  Goodbye! 🏹\n"); break
        elif choice == "1": menu_seed()
        elif choice == "2": menu_archer()
        elif choice == "3": menu_rounds()
        elif choice == "4": menu_competitions()
        elif choice == "5": menu_club_records()
        else: print("  Unknown option — try again.")


if __name__ == "__main__":
    main()