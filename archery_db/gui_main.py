#!/usr/bin/env python3
# gui_main.py
"""
Archery Score Recording System — CustomTkinter GUI
---------------------------------------------------
Mirrors the functionality of main.py / data_entry.py with a full
graphical interface built on CustomTkinter.

Run with:  python gui_main.py
           (from the archery_db/ directory, or the project root)

Requirements:
    pip install customtkinter
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from datetime import datetime, date
from typing import Optional, List

# ---------------------------------------------------------------------------
# Path setup – works from project root or archery_db/
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ARCHERY_DB = os.path.join(_HERE, "archery_db")
for _p in (_ARCHERY_DB, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from database import init_db, get_connection
from repositories import (
    ArcherRepository, RoundRepository,
    ScoreRepository, CompetitionRepository,
)
from models import Archer, Round, RangeDefinition, Score, End
from config import Gender, AgeClass, Equipment
import services

# ---------------------------------------------------------------------------
# App-wide appearance
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

FONT_TITLE  = ("Helvetica", 20, "bold")
FONT_HEADER = ("Helvetica", 14, "bold")
FONT_BODY   = ("Helvetica", 13)
FONT_MONO   = ("Courier", 12)

ACCENT    = "#1f6aa5"
SUCCESS   = "#2ecc71"
WARNING   = "#e67e22"
DANGER    = "#e74c3c"
BG_CARD   = "#2b2b2b"


# ===========================================================================
# Reusable widgets
# ===========================================================================

class ScrollableTable(ctk.CTkScrollableFrame):
    """A scrollable frame that renders a list-of-dicts as a table."""

    def __init__(self, master, columns: list, **kwargs):
        super().__init__(master, **kwargs)
        self.columns = columns
        self._build_header()

    def _build_header(self):
        for col, (label, width) in enumerate(self.columns):
            ctk.CTkLabel(
                self, text=label, font=FONT_HEADER,
                width=width, anchor="w",
            ).grid(row=0, column=col, padx=4, pady=(4, 2), sticky="w")
        # separator
        sep = ctk.CTkFrame(self, height=2, fg_color=ACCENT)
        sep.grid(row=1, column=0, columnspan=len(self.columns),
                 sticky="ew", padx=4, pady=2)

    def populate(self, rows: list):
        """rows = list of tuples/lists aligned with self.columns."""
        # Clear old data rows (keep header = rows 0,1)
        for widget in self.winfo_children():
            info = widget.grid_info()
            if info and int(info.get("row", 0)) > 1:
                widget.destroy()

        for r_idx, row in enumerate(rows):
            for c_idx, (_, width) in enumerate(self.columns):
                val = row[c_idx] if c_idx < len(row) else ""
                ctk.CTkLabel(
                    self, text=str(val), font=FONT_MONO,
                    width=width, anchor="w",
                ).grid(row=r_idx + 2, column=c_idx, padx=4, pady=1, sticky="w")


class LabeledEntry(ctk.CTkFrame):
    """Label + Entry pair."""
    def __init__(self, master, label: str, default: str = "", width: int = 200, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        ctk.CTkLabel(self, text=label, font=FONT_BODY, width=160, anchor="w").pack(side="left")
        self.entry = ctk.CTkEntry(self, width=width)
        self.entry.insert(0, default)
        self.entry.pack(side="left", padx=(4, 0))

    @property
    def value(self) -> str:
        return self.entry.get().strip()

    def set(self, v: str):
        self.entry.delete(0, "end")
        self.entry.insert(0, str(v))


class LabeledCombo(ctk.CTkFrame):
    """Label + OptionMenu pair for enum selection."""
    def __init__(self, master, label: str, options: list, default: str = "", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        ctk.CTkLabel(self, text=label, font=FONT_BODY, width=160, anchor="w").pack(side="left")
        self._var = ctk.StringVar(value=default or (options[0] if options else ""))
        self.combo = ctk.CTkOptionMenu(self, variable=self._var, values=options, width=200)
        self.combo.pack(side="left", padx=(4, 0))

    @property
    def value(self) -> str:
        return self._var.get()

    def set(self, v: str):
        self._var.set(v)


def show_info(title: str, message: str):
    messagebox.showinfo(title, message)

def show_error(title: str, message: str):
    messagebox.showerror(title, message)

def ask_yes_no(title: str, message: str) -> bool:
    return messagebox.askyesno(title, message)


# ===========================================================================
# Section frames (one per main-menu item)
# ===========================================================================

class SeedFrame(ctk.CTkFrame):
    """1 — Seed database."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="🏹  Seed Database", font=FONT_TITLE).pack(pady=(20, 6))
        ctk.CTkLabel(
            self,
            text="Populate the database with rounds, archers, practice scores and competitions.\n"
                 "Existing data is NOT wiped first.",
            font=FONT_BODY, wraplength=500,
        ).pack(pady=(0, 16))

        form = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
        form.pack(padx=40, pady=10, fill="x")

        self.num_archers = LabeledEntry(form, "Archers to generate:", "50")
        self.num_archers.pack(padx=20, pady=8, anchor="w")

        self.scores_each = LabeledEntry(form, "Practice scores each:", "10")
        self.scores_each.pack(padx=20, pady=8, anchor="w")

        self.num_comps = LabeledEntry(form, "Competitions:", "8")
        self.num_comps.pack(padx=20, pady=8, anchor="w")

        self.progress = ctk.CTkProgressBar(self, width=400)
        self.progress.set(0)
        self.progress.pack(pady=10)

        self.status_label = ctk.CTkLabel(self, text="", font=FONT_BODY)
        self.status_label.pack()

        ctk.CTkButton(
            self, text="▶  Run Seed", command=self._run_seed,
            fg_color=SUCCESS, hover_color="#27ae60", font=FONT_HEADER,
        ).pack(pady=20)

    def _run_seed(self):
        try:
            na = int(self.num_archers.value)
            se = int(self.scores_each.value)
            nc = int(self.num_comps.value)
        except ValueError:
            show_error("Input error", "All fields must be whole numbers.")
            return

        self.progress.set(0.1)
        self.status_label.configure(text="Seeding rounds…")
        self.update()

        from data_generator import ArcheryDataGenerator
        gen = ArcheryDataGenerator()

        self.progress.set(0.25); self.status_label.configure(text="Seeding rounds…"); self.update()
        rounds = gen.seed_rounds()
        self.progress.set(0.35); self.status_label.configure(text="Seeding equivalent rounds…"); self.update()
        gen.seed_equivalent_rounds()
        self.progress.set(0.5); self.status_label.configure(text=f"Generating {na} archers…"); self.update()
        gen.generate_archers(na)
        self.progress.set(0.75); self.status_label.configure(text="Generating practice scores…"); self.update()
        gen.generate_scores_for_all_archers(rounds, se)
        self.progress.set(0.9); self.status_label.configure(text="Generating competitions…"); self.update()
        gen.generate_competitions(rounds, nc)

        self.progress.set(1.0)
        self.status_label.configure(text="✅  Database seeding complete!")
        show_info("Done", "Database seeded successfully.")


# ---------------------------------------------------------------------------

class ArcherLookupFrame(ctk.CTkFrame):
    """2 — Archer lookup."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="🏹  Archer Lookup", font=FONT_TITLE).pack(pady=(20, 10))

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=20, pady=10)

        self._build_list_tab(tabs.add("All Archers"))
        self._build_scores_tab(tabs.add("Archer Scores"))
        self._build_pb_tab(tabs.add("Personal Best"))

    # --- All Archers ---
    def _build_list_tab(self, tab):
        ctk.CTkButton(
            tab, text="Load / Refresh", command=self._load_archers,
            width=160,
        ).pack(pady=10)

        self.archer_table = ScrollableTable(
            tab,
            columns=[
                ("ID", 60), ("Name", 200), ("Gender", 90),
                ("Age Class", 110), ("Equipment", 160),
            ],
            height=420,
        )
        self.archer_table.pack(fill="both", expand=True, padx=10, pady=6)

    def _load_archers(self):
        archers = ArcherRepository.list_all()
        rows = [
            (a.id, a.full_name, a.gender.value, a.age_class.value, a.default_equipment.value)
            for a in archers
        ]
        self.archer_table.populate(rows)

    # --- Archer Scores ---
    def _build_scores_tab(self, tab):
        filters = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=10)
        filters.pack(fill="x", padx=10, pady=8)

        self.sc_archer_id  = LabeledEntry(filters, "Archer ID:", width=100)
        self.sc_archer_id.pack(padx=16, pady=4, anchor="w")

        self.sc_round      = LabeledEntry(filters, "Round name (optional):", width=160)
        self.sc_round.pack(padx=16, pady=4, anchor="w")

        self.sc_from       = LabeledEntry(filters, "From date (YYYY-MM-DD):", width=160)
        self.sc_from.pack(padx=16, pady=4, anchor="w")

        self.sc_to         = LabeledEntry(filters, "To date   (YYYY-MM-DD):", width=160)
        self.sc_to.pack(padx=16, pady=4, anchor="w")

        self.sc_sort       = LabeledCombo(filters, "Sort by:", ["date", "score"], "date")
        self.sc_sort.pack(padx=16, pady=4, anchor="w")

        self.sc_limit      = LabeledEntry(filters, "Max results:", "20", width=80)
        self.sc_limit.pack(padx=16, pady=4, anchor="w")

        ctk.CTkButton(
            tab, text="Search", command=self._load_scores, width=140,
        ).pack(pady=8)

        self.score_table = ScrollableTable(
            tab,
            columns=[
                ("ID", 60), ("Date", 150), ("Round", 160),
                ("Equipment", 150), ("Score", 70), ("Comp?", 60),
            ],
            height=340,
        )
        self.score_table.pack(fill="both", expand=True, padx=10, pady=4)

    def _load_scores(self):
        try:
            archer_id = int(self.sc_archer_id.value)
        except ValueError:
            show_error("Input", "Enter a valid Archer ID."); return

        from_dt = to_dt = None
        try:
            if self.sc_from.value:
                from_dt = datetime.strptime(self.sc_from.value, "%Y-%m-%d")
            if self.sc_to.value:
                to_dt = datetime.strptime(self.sc_to.value, "%Y-%m-%d")
        except ValueError:
            show_error("Date format", "Use YYYY-MM-DD."); return

        limit = int(self.sc_limit.value or 20)
        round_name = self.sc_round.value or None
        round_id = None
        if round_name:
            r = RoundRepository.get_by_name(round_name)
            round_id = r.id if r else None

        scores = ScoreRepository.get_by_archer(
            archer_id, limit=limit, round_id=round_id,
            from_date=from_dt, to_date=to_dt,
            sort_by=self.sc_sort.value, sort_desc=True,
        )
        rows = []
        for s in scores:
            r = RoundRepository.get_by_id(s.round_id)
            rows.append((
                s.id, str(s.date_shot)[:19],
                r.name if r else f"ID {s.round_id}",
                s.equipment.value, s.total_score,
                "Yes" if s.is_competition else "-",
            ))
        self.score_table.populate(rows)

    # --- Personal Best ---
    def _build_pb_tab(self, tab):
        f = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=10)
        f.pack(fill="x", padx=10, pady=16)

        self.pb_archer_id = LabeledEntry(f, "Archer ID:")
        self.pb_archer_id.pack(padx=16, pady=6, anchor="w")

        self.pb_round = LabeledEntry(f, "Round name:", width=180)
        self.pb_round.pack(padx=16, pady=6, anchor="w")

        ctk.CTkButton(tab, text="Look up PB", command=self._look_pb, width=140).pack(pady=10)

        self.pb_result = ctk.CTkLabel(tab, text="", font=FONT_BODY, wraplength=500)
        self.pb_result.pack(pady=6)

    def _look_pb(self):
        try:
            archer_id = int(self.pb_archer_id.value)
        except ValueError:
            show_error("Input", "Enter a valid Archer ID."); return
        round_name = self.pb_round.value
        if not round_name:
            show_error("Input", "Enter a round name."); return

        archer = ArcherRepository.get_by_id(archer_id)
        r = RoundRepository.get_by_name(round_name)
        if not archer:
            self.pb_result.configure(text="Archer not found."); return
        if not r:
            self.pb_result.configure(text=f"Round '{round_name}' not found."); return

        pb = ScoreRepository.get_personal_best(archer_id, r.id)
        if not pb:
            self.pb_result.configure(text=f"No scores for {archer.full_name} on {round_name}.")
        else:
            self.pb_result.configure(
                text=f"PB for {archer.full_name} on {round_name}:\n"
                     f"  Score: {pb.total_score}   Date: {str(pb.date_shot)[:10]}"
            )


# ---------------------------------------------------------------------------

class RoundLookupFrame(ctk.CTkFrame):
    """3 — Round lookup."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="🏹  Round Lookup", font=FONT_TITLE).pack(pady=(20, 10))

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=20, pady=10)

        self._build_list_tab(tabs.add("All Rounds"))
        self._build_def_tab(tabs.add("Round Definition"))
        self._build_equiv_tab(tabs.add("Equivalent Round"))

    def _build_list_tab(self, tab):
        ctk.CTkButton(tab, text="Load / Refresh", command=self._load_rounds, width=160).pack(pady=10)
        self.round_table = ScrollableTable(
            tab,
            columns=[
                ("ID", 60), ("Name", 160), ("Arrows", 70),
                ("Max Score", 90), ("Ranges", 260),
            ],
            height=420,
        )
        self.round_table.pack(fill="both", expand=True, padx=10, pady=6)

    def _load_rounds(self):
        rounds = RoundRepository.list_all()
        rows = []
        for r in rounds:
            summary = ", ".join(f"{rd.distance}m×{rd.ends}ends" for rd in r.ranges)
            rows.append((r.id, r.name, r.total_arrows, r.possible_score, summary))
        self.round_table.populate(rows)

    def _build_def_tab(self, tab):
        f = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=10)
        f.pack(fill="x", padx=10, pady=12)

        self.def_name = LabeledEntry(f, "Round name:", width=200)
        self.def_name.pack(padx=16, pady=8, anchor="w")

        ctk.CTkButton(tab, text="Look up", command=self._look_def, width=130).pack(pady=8)

        self.def_result = ctk.CTkTextbox(tab, height=220, font=FONT_MONO)
        self.def_result.pack(fill="x", padx=10, pady=4)

    def _look_def(self):
        name = self.def_name.value
        r = RoundRepository.get_by_name(name)
        self.def_result.delete("1.0", "end")
        if not r:
            self.def_result.insert("end", f"Round '{name}' not found.")
            return
        lines = [
            f"Round  : {r.name}  (ID {r.id})",
            f"Arrows : {r.total_arrows}   Max score: {r.possible_score}",
            "",
            f"{'Range':<8} {'Dist':>6}  {'Ends':>5}  {'Arrows/End':>10}  {'Face cm':>8}",
            "-" * 48,
        ]
        for i, rd in enumerate(r.ranges, 1):
            lines.append(f"{i:<8} {rd.distance:>5}m  {rd.ends:>5}  {rd.arrows_per_end:>10}  {rd.face_size:>8}")
        self.def_result.insert("end", "\n".join(lines))

    def _build_equiv_tab(self, tab):
        f = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=10)
        f.pack(fill="x", padx=10, pady=12)

        self.eq_base   = LabeledEntry(f, "Base round name:", width=200)
        self.eq_base.pack(padx=16, pady=6, anchor="w")

        self.eq_gender = LabeledCombo(f, "Gender:", [g.value for g in Gender])
        self.eq_gender.pack(padx=16, pady=6, anchor="w")

        self.eq_age    = LabeledCombo(f, "Age class:", [a.value for a in AgeClass])
        self.eq_age.pack(padx=16, pady=6, anchor="w")

        self.eq_equip  = LabeledCombo(f, "Equipment:", [e.value for e in Equipment])
        self.eq_equip.pack(padx=16, pady=6, anchor="w")

        self.eq_as_of  = LabeledEntry(f, "As-of date (YYYY-MM-DD):", width=160)
        self.eq_as_of.pack(padx=16, pady=6, anchor="w")

        ctk.CTkButton(tab, text="Find equivalent", command=self._look_equiv, width=160).pack(pady=8)

        self.eq_result = ctk.CTkLabel(tab, text="", font=FONT_BODY, wraplength=500)
        self.eq_result.pack(pady=6)

    def _look_equiv(self):
        base_name = self.eq_base.value
        base = RoundRepository.get_by_name(base_name)
        if not base:
            self.eq_result.configure(text=f"Base round '{base_name}' not found.")
            return

        gender    = Gender(self.eq_gender.value)
        age_class = AgeClass(self.eq_age.value)
        equipment = Equipment(self.eq_equip.value)

        as_of = None
        if self.eq_as_of.value:
            try:
                as_of = date.fromisoformat(self.eq_as_of.value)
            except ValueError:
                show_error("Date", "Use YYYY-MM-DD."); return

        equiv = RoundRepository.get_equivalent_round(base.id, gender, age_class, equipment, as_of=as_of)
        cat = f"{gender.value} {age_class.value} {equipment.value}"
        if equiv:
            self.eq_result.configure(
                text=f"Category  : {cat}\nBase round: {base_name}\nEquivalent: {equiv.name}"
            )
        else:
            self.eq_result.configure(
                text=f"No equivalent round for {cat} on {base_name}.\n"
                     f"→ This category shoots the base round unchanged."
            )


# ---------------------------------------------------------------------------

class CompetitionFrame(ctk.CTkFrame):
    """4 — Competition lookup."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="🏹  Competitions", font=FONT_TITLE).pack(pady=(20, 10))

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=20, pady=10)

        self._build_list_tab(tabs.add("All Competitions"))
        self._build_leaderboard_tab(tabs.add("Leaderboard"))
        self._build_championship_tab(tabs.add("Championship Results"))

    def _build_list_tab(self, tab):
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(pady=8)
        self.champ_only_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row, text="Championship only", variable=self.champ_only_var).pack(side="left", padx=10)
        ctk.CTkButton(row, text="Load / Refresh", command=self._load_comps, width=150).pack(side="left")

        self.comp_table = ScrollableTable(
            tab,
            columns=[("ID", 60), ("Date", 110), ("Champ?", 70), ("Name", 300)],
            height=420,
        )
        self.comp_table.pack(fill="both", expand=True, padx=10, pady=6)

    def _load_comps(self):
        comps = CompetitionRepository.list_all(championship_only=self.champ_only_var.get())
        rows = [
            (c["id"], c["date"], "Yes" if c.get("is_championship") else "-", c["name"])
            for c in comps
        ]
        self.comp_table.populate(rows)

    def _build_leaderboard_tab(self, tab):
        f = ctk.CTkFrame(tab, fg_color=BG_CARD, corner_radius=10)
        f.pack(fill="x", padx=10, pady=10)

        self.lb_comp_id = LabeledEntry(f, "Competition ID:", width=100)
        self.lb_comp_id.pack(padx=16, pady=8, anchor="w")

        ctk.CTkButton(tab, text="Load Leaderboard", command=self._load_leaderboard, width=160).pack(pady=8)

        self.lb_title = ctk.CTkLabel(tab, text="", font=FONT_HEADER)
        self.lb_title.pack()

        self.lb_table = ScrollableTable(
            tab,
            columns=[("Rank", 50), ("Name", 200), ("Equipment", 150), ("Score", 80)],
            height=360,
        )
        self.lb_table.pack(fill="both", expand=True, padx=10, pady=4)

    def _load_leaderboard(self):
        try:
            comp_id = int(self.lb_comp_id.value)
        except ValueError:
            show_error("Input", "Enter a valid Competition ID."); return

        comp = CompetitionRepository.get_by_id(comp_id)
        if not comp:
            show_error("Not found", f"Competition {comp_id} not found."); return

        self.lb_title.configure(text=f"{comp['name']}  ({comp['date']})")
        results = CompetitionRepository.get_leaderboard(comp_id)
        rows = [
            (rank, archer.full_name, score.equipment.value, score.total_score)
            for rank, (score, archer) in enumerate(results, 1)
        ]
        self.lb_table.populate(rows)

    def _build_championship_tab(self, tab):
        ctk.CTkButton(
            tab, text="Load Championship Results",
            command=self._load_champ, width=220,
        ).pack(pady=10)

        self.champ_table = ScrollableTable(
            tab,
            columns=[("Rank", 50), ("Name", 200), ("Comps Shot", 90), ("Total Score", 100)],
            height=420,
        )
        self.champ_table.pack(fill="both", expand=True, padx=10, pady=4)

    def _load_champ(self):
        results = CompetitionRepository.get_championship_results()
        rows = [
            (rank, row["archer"].full_name, row["competitions_shot"], row["total_score"])
            for rank, row in enumerate(results, 1)
        ]
        self.champ_table.populate(rows)


# ---------------------------------------------------------------------------

class ClubRecordsFrame(ctk.CTkFrame):
    """5 — Club records."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="🏹  Club Records", font=FONT_TITLE).pack(pady=(20, 10))

        f = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
        f.pack(padx=40, pady=16, fill="x")

        self.round_name = LabeledEntry(f, "Round name:", width=200)
        self.round_name.pack(padx=20, pady=10, anchor="w")

        ctk.CTkButton(self, text="Look up Club Best", command=self._look_best, width=180).pack(pady=8)

        self.result = ctk.CTkLabel(self, text="", font=FONT_BODY, wraplength=520)
        self.result.pack(pady=10)

    def _look_best(self):
        name = self.round_name.value
        r = RoundRepository.get_by_name(name)
        if not r:
            self.result.configure(text=f"Round '{name}' not found."); return
        res = ScoreRepository.get_club_best(r.id)
        if not res:
            self.result.configure(text=f"No scores recorded for {name}."); return
        score, archer = res
        self.result.configure(
            text=f"Club best for {name}:\n"
                 f"  Score : {score.total_score}\n"
                 f"  Archer: {archer.full_name}\n"
                 f"  Date  : {str(score.date_shot)[:10]}"
        )


# ---------------------------------------------------------------------------
# Data entry frames
# ---------------------------------------------------------------------------

class AddArcherFrame(ctk.CTkFrame):
    """Recorder — Add / edit an archer."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="Add New Archer", font=FONT_HEADER).pack(pady=(16, 8))

        f = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        f.pack(padx=20, pady=8, fill="x")

        self.first_name = LabeledEntry(f, "First name:", width=180)
        self.first_name.pack(padx=16, pady=5, anchor="w")

        self.last_name  = LabeledEntry(f, "Last name:", width=180)
        self.last_name.pack(padx=16, pady=5, anchor="w")

        self.gender     = LabeledCombo(f, "Gender:", [g.value for g in Gender])
        self.gender.pack(padx=16, pady=5, anchor="w")

        self.age_class  = LabeledCombo(f, "Age class:", [a.value for a in AgeClass])
        self.age_class.pack(padx=16, pady=5, anchor="w")

        self.equipment  = LabeledCombo(f, "Default equipment:", [e.value for e in Equipment])
        self.equipment.pack(padx=16, pady=5, anchor="w")

        self.dob        = LabeledEntry(f, "Date of birth (YYYY-MM-DD):", width=160)
        self.dob.pack(padx=16, pady=5, anchor="w")

        ctk.CTkButton(
            self, text="💾  Save Archer", command=self._save,
            fg_color=SUCCESS, hover_color="#27ae60",
        ).pack(pady=12)

    def _save(self):
        fn = self.first_name.value
        ln = self.last_name.value
        if not fn or not ln:
            show_error("Required", "First and last name are required."); return
        dob = None
        if self.dob.value:
            try:
                dob = date.fromisoformat(self.dob.value)
            except ValueError:
                show_error("Date", "Use YYYY-MM-DD."); return

        archer = Archer(
            first_name=fn, last_name=ln,
            gender=Gender(self.gender.value),
            age_class=AgeClass(self.age_class.value),
            default_equipment=Equipment(self.equipment.value),
            date_of_birth=dob,
        )
        if ask_yes_no("Confirm", f"Save archer {fn} {ln}?"):
            aid = ArcherRepository.create(archer)
            show_info("Saved", f"Archer saved with ID {aid}.")
            # clear form
            for w in (self.first_name, self.last_name, self.dob):
                w.set("")


class AddRoundFrame(ctk.CTkFrame):
    """Recorder — Add a new round definition."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="Add New Round", font=FONT_HEADER).pack(pady=(16, 8))

        top = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        top.pack(padx=20, pady=6, fill="x")

        self.round_name  = LabeledEntry(top, "Round name:", width=200)
        self.round_name.pack(padx=16, pady=6, anchor="w")

        self.num_ranges  = LabeledEntry(top, "Number of ranges:", default="2", width=80)
        self.num_ranges.pack(padx=16, pady=6, anchor="w")

        self.valid_from  = LabeledEntry(top, "Valid from (YYYY-MM-DD):", width=160)
        self.valid_from.pack(padx=16, pady=6, anchor="w")

        ctk.CTkButton(self, text="Build range fields", command=self._build_ranges, width=180).pack(pady=6)

        self.ranges_frame = ctk.CTkScrollableFrame(self, height=200)
        self.ranges_frame.pack(fill="x", padx=20, pady=4)

        self._range_widgets: List[dict] = []

        ctk.CTkButton(
            self, text="💾  Save Round", command=self._save,
            fg_color=SUCCESS, hover_color="#27ae60",
        ).pack(pady=12)

    def _build_ranges(self):
        for w in self.ranges_frame.winfo_children():
            w.destroy()
        self._range_widgets = []
        try:
            n = max(1, min(10, int(self.num_ranges.value)))
        except ValueError:
            show_error("Input", "Enter a valid number."); return

        for i in range(1, n + 1):
            row = ctk.CTkFrame(self.ranges_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"Range {i}:", font=FONT_BODY, width=70).pack(side="left")
            dist_e = ctk.CTkEntry(row, placeholder_text="dist (m)", width=90)
            dist_e.pack(side="left", padx=4)
            ends_e = ctk.CTkEntry(row, placeholder_text="ends (5/6)", width=90)
            ends_e.pack(side="left", padx=4)
            face_e = ctk.CTkEntry(row, placeholder_text="face (80/122)", width=100)
            face_e.pack(side="left", padx=4)
            self._range_widgets.append({"dist": dist_e, "ends": ends_e, "face": face_e})

    def _save(self):
        name = self.round_name.value
        if not name:
            show_error("Required", "Round name is required."); return
        if RoundRepository.get_by_name(name):
            show_error("Exists", f"Round '{name}' already exists."); return
        if not self._range_widgets:
            show_error("Required", "Build range fields first."); return

        ranges: List[RangeDefinition] = []
        try:
            for i, rw in enumerate(self._range_widgets, 1):
                dist = int(rw["dist"].get())
                ends = int(rw["ends"].get())
                face_raw = int(rw["face"].get())
                face = 122 if face_raw >= 100 else 80
                ranges.append(RangeDefinition(distance=dist, ends=ends, face_size=face))
        except ValueError:
            show_error("Input", "All range fields must be whole numbers."); return

        total_arrows   = sum(r.ends * 6 for r in ranges)
        possible_score = total_arrows * 10
        valid_from = None
        if self.valid_from.value:
            try:
                valid_from = date.fromisoformat(self.valid_from.value)
            except ValueError:
                show_error("Date", "Use YYYY-MM-DD."); return

        round_obj = Round(
            name=name, total_arrows=total_arrows,
            possible_score=possible_score, ranges=ranges, valid_from=valid_from,
        )
        if ask_yes_no("Confirm", f"Save round '{name}' ({total_arrows} arrows, max {possible_score})?"):
            rid = RoundRepository.create(round_obj)
            show_info("Saved", f"Round saved with ID {rid}.")
            self.round_name.set("")


class AddCompetitionFrame(ctk.CTkFrame):
    """Recorder — Add a new competition."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="Add New Competition", font=FONT_HEADER).pack(pady=(16, 8))

        f = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        f.pack(padx=20, pady=8, fill="x")

        self.comp_name  = LabeledEntry(f, "Competition name:", width=240)
        self.comp_name.pack(padx=16, pady=6, anchor="w")

        self.comp_date  = LabeledEntry(f, "Date (YYYY-MM-DD):", width=160,
                                       default=date.today().isoformat())
        self.comp_date.pack(padx=16, pady=6, anchor="w")

        self.round_name = LabeledEntry(f, "Round name:", width=200)
        self.round_name.pack(padx=16, pady=6, anchor="w")

        self.is_champ_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(f, text="Part of club championship", variable=self.is_champ_var).pack(
            padx=16, pady=8, anchor="w")

        ctk.CTkButton(
            self, text="💾  Save Competition", command=self._save,
            fg_color=SUCCESS, hover_color="#27ae60",
        ).pack(pady=12)

    def _save(self):
        name = self.comp_name.value
        if not name:
            show_error("Required", "Competition name required."); return
        try:
            comp_date = date.fromisoformat(self.comp_date.value)
        except ValueError:
            show_error("Date", "Use YYYY-MM-DD."); return

        r = RoundRepository.get_by_name(self.round_name.value)
        if not r:
            show_error("Round", f"Round '{self.round_name.value}' not found."); return

        if ask_yes_no("Confirm", f"Save competition '{name}'?"):
            cid = CompetitionRepository.create(
                name, comp_date, r.id, is_championship=self.is_champ_var.get()
            )
            show_info("Saved", f"Competition saved with ID {cid}.")
            self.comp_name.set("")


class DirectScoreEntry(ctk.CTkFrame):
    """Recorder — Enter a score directly (paper scorecard)."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="Direct Score Entry", font=FONT_HEADER).pack(pady=(16, 6))

        top = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        top.pack(padx=20, pady=6, fill="x")

        self.archer_id   = LabeledEntry(top, "Archer ID:", width=100)
        self.archer_id.pack(padx=16, pady=5, anchor="w")

        self.round_name  = LabeledEntry(top, "Round name:", width=200)
        self.round_name.pack(padx=16, pady=5, anchor="w")

        self.equipment   = LabeledCombo(top, "Equipment:", [e.value for e in Equipment])
        self.equipment.pack(padx=16, pady=5, anchor="w")

        self.date_shot   = LabeledEntry(top, "Date shot (YYYY-MM-DD):", width=160,
                                        default=date.today().isoformat())
        self.date_shot.pack(padx=16, pady=5, anchor="w")

        self.is_comp_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(top, text="Competition score", variable=self.is_comp_var).pack(
            padx=16, pady=5, anchor="w")

        self.comp_id_e   = LabeledEntry(top, "Competition ID (if comp):", width=100)
        self.comp_id_e.pack(padx=16, pady=5, anchor="w")

        self.notes       = LabeledEntry(top, "Notes:", width=280)
        self.notes.pack(padx=16, pady=5, anchor="w")

        ctk.CTkButton(self, text="Build End Entry Fields", command=self._build_ends, width=200).pack(pady=6)

        self.ends_frame = ctk.CTkScrollableFrame(self, height=220)
        self.ends_frame.pack(fill="x", padx=20, pady=4)

        self._end_entries: List[ctk.CTkEntry] = []

        ctk.CTkButton(
            self, text="💾  Save Score", command=self._save_score,
            fg_color=SUCCESS, hover_color="#27ae60",
        ).pack(pady=10)

    def _build_ends(self):
        for w in self.ends_frame.winfo_children():
            w.destroy()
        self._end_entries = []

        round_obj = RoundRepository.get_by_name(self.round_name.value)
        if not round_obj:
            show_error("Round", f"Round '{self.round_name.value}' not found."); return

        for rng_idx, rng_def in enumerate(round_obj.ranges, 1):
            ctk.CTkLabel(
                self.ends_frame,
                text=f"Range {rng_idx}: {rng_def.distance}m, {rng_def.ends} ends, {rng_def.face_size}cm",
                font=FONT_BODY,
            ).pack(anchor="w", padx=6, pady=(6, 2))

            for end_num in range(1, rng_def.ends + 1):
                row = ctk.CTkFrame(self.ends_frame, fg_color="transparent")
                row.pack(fill="x", pady=1)
                ctk.CTkLabel(
                    row, text=f"  End {end_num} (6 arrows):", font=FONT_MONO, width=160, anchor="w"
                ).pack(side="left")
                e = ctk.CTkEntry(row, placeholder_text="e.g. 10 9 9 8 7 6", width=220)
                e.pack(side="left", padx=4)
                self._end_entries.append({
                    "entry": e, "range_number": rng_idx, "end_number": end_num,
                })

    def _save_score(self):
        try:
            archer_id = int(self.archer_id.value)
        except ValueError:
            show_error("Input", "Enter a valid Archer ID."); return

        archer = ArcherRepository.get_by_id(archer_id)
        if not archer:
            show_error("Not found", f"Archer {archer_id} not found."); return

        round_obj = RoundRepository.get_by_name(self.round_name.value)
        if not round_obj:
            show_error("Round", f"Round not found."); return

        if not self._end_entries:
            show_error("Missing", "Build end fields first."); return

        ends: List[End] = []
        try:
            for info in self._end_entries:
                raw = info["entry"].get().strip().split()
                if len(raw) != 6:
                    raise ValueError(f"Need 6 arrows for Range {info['range_number']} End {info['end_number']}")
                arrows = sorted([int(x) for x in raw], reverse=True)
                if any(a < 0 or a > 10 for a in arrows):
                    raise ValueError("Arrow scores must be 0–10")
                ends.append(End(end_number=info["end_number"],
                                range_number=info["range_number"],
                                arrows=arrows))
        except ValueError as e:
            show_error("Input error", str(e)); return

        total = sum(sum(e.arrows) for e in ends)
        try:
            ds = datetime.strptime(self.date_shot.value, "%Y-%m-%d")
        except ValueError:
            show_error("Date", "Use YYYY-MM-DD."); return

        is_comp = self.is_comp_var.get()
        comp_id = None
        if is_comp and self.comp_id_e.value:
            try:
                comp_id = int(self.comp_id_e.value)
            except ValueError:
                pass

        if not ask_yes_no("Confirm", f"Save score {total} for {archer.full_name}?"):
            return

        score = Score(
            archer_id=archer_id,
            round_id=round_obj.id,
            equipment=Equipment(self.equipment.value),
            date_shot=ds,
            is_competition=is_comp,
            competition_id=comp_id,
            total_score=total,
            ends=ends,
            notes=self.notes.value,
        )
        ScoreRepository.save(score)
        show_info("Saved", f"Score {total} saved (ID {score.id}).")


class StageScoreFrame(ctk.CTkFrame):
    """Archer self-entry — stage a score."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="Stage a Score (Archer Self-Entry)", font=FONT_HEADER).pack(pady=(16, 6))

        top = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        top.pack(padx=20, pady=6, fill="x")

        self.archer_id  = LabeledEntry(top, "Your Archer ID:", width=100)
        self.archer_id.pack(padx=16, pady=5, anchor="w")

        self.round_name = LabeledEntry(top, "Round name:", width=200)
        self.round_name.pack(padx=16, pady=5, anchor="w")

        self.equipment  = LabeledCombo(top, "Equipment:", [e.value for e in Equipment])
        self.equipment.pack(padx=16, pady=5, anchor="w")

        self.date_shot  = LabeledEntry(top, "Date shot (YYYY-MM-DD):", width=160,
                                       default=date.today().isoformat())
        self.date_shot.pack(padx=16, pady=5, anchor="w")

        self.is_comp_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(top, text="Competition score", variable=self.is_comp_var).pack(
            padx=16, pady=5, anchor="w")

        self.notes = LabeledEntry(top, "Notes:", width=280)
        self.notes.pack(padx=16, pady=5, anchor="w")

        ctk.CTkButton(self, text="Build End Entry Fields", command=self._build_ends, width=200).pack(pady=6)

        self.ends_frame = ctk.CTkScrollableFrame(self, height=200)
        self.ends_frame.pack(fill="x", padx=20, pady=4)

        self._end_entries: List[dict] = []

        ctk.CTkButton(
            self, text="📤  Submit for Approval", command=self._submit,
            fg_color=WARNING, hover_color="#d35400",
        ).pack(pady=10)

    def _build_ends(self):
        for w in self.ends_frame.winfo_children():
            w.destroy()
        self._end_entries = []

        round_obj = RoundRepository.get_by_name(self.round_name.value)
        if not round_obj:
            show_error("Round", f"Round '{self.round_name.value}' not found."); return

        for rng_idx, rng_def in enumerate(round_obj.ranges, 1):
            ctk.CTkLabel(
                self.ends_frame,
                text=f"Range {rng_idx}: {rng_def.distance}m, {rng_def.ends} ends",
                font=FONT_BODY,
            ).pack(anchor="w", padx=6, pady=(6, 2))
            for end_num in range(1, rng_def.ends + 1):
                row = ctk.CTkFrame(self.ends_frame, fg_color="transparent")
                row.pack(fill="x", pady=1)
                ctk.CTkLabel(row, text=f"  End {end_num} (6 arrows):", font=FONT_MONO, width=160, anchor="w").pack(side="left")
                e = ctk.CTkEntry(row, placeholder_text="e.g. 10 9 8 8 7 6", width=220)
                e.pack(side="left", padx=4)
                self._end_entries.append({"entry": e, "range_number": rng_idx, "end_number": end_num})

    def _submit(self):
        from data_entry import _ensure_staged_scores_table, _save_staged_score
        try:
            archer_id = int(self.archer_id.value)
        except ValueError:
            show_error("Input", "Enter a valid Archer ID."); return
        archer = ArcherRepository.get_by_id(archer_id)
        if not archer:
            show_error("Not found", "Archer not found."); return
        round_obj = RoundRepository.get_by_name(self.round_name.value)
        if not round_obj:
            show_error("Round", "Round not found."); return
        if not self._end_entries:
            show_error("Missing", "Build end fields first."); return

        ends: List[End] = []
        try:
            for info in self._end_entries:
                raw = info["entry"].get().strip().split()
                if len(raw) != 6:
                    raise ValueError(f"Need 6 arrows for Range {info['range_number']} End {info['end_number']}")
                arrows = sorted([int(x) for x in raw], reverse=True)
                if any(a < 0 or a > 10 for a in arrows):
                    raise ValueError("Arrow scores must be 0–10")
                ends.append(End(end_number=info["end_number"], range_number=info["range_number"], arrows=arrows))
        except ValueError as e:
            show_error("Input error", str(e)); return

        total = sum(sum(e.arrows) for e in ends)
        try:
            ds = datetime.strptime(self.date_shot.value, "%Y-%m-%d")
        except ValueError:
            show_error("Date", "Use YYYY-MM-DD."); return

        if not ask_yes_no("Confirm", f"Submit score {total} for {archer.full_name} for recorder approval?"):
            return

        _ensure_staged_scores_table()
        sid = _save_staged_score(
            archer_id=archer_id, round_id=round_obj.id,
            equipment=Equipment(self.equipment.value),
            date_shot=ds, ends=ends,
            is_competition=self.is_comp_var.get(),
            notes=self.notes.value,
        )
        show_info("Submitted", f"Score staged (ID {sid}). A recorder will review it.")


class ApproveStagedFrame(ctk.CTkFrame):
    """Recorder — Approve / reject staged scores."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="Approve / Reject Staged Scores", font=FONT_HEADER).pack(pady=(16, 8))

        ctk.CTkButton(self, text="Load Pending Staged Scores", command=self._load, width=230).pack(pady=6)

        self.staged_table = ScrollableTable(
            self,
            columns=[
                ("ID", 55), ("Archer", 180), ("Round", 150),
                ("Equipment", 140), ("Date Shot", 140), ("Comp?", 60),
            ],
            height=240,
        )
        self.staged_table.pack(fill="x", padx=16, pady=6)

        action_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=10)
        action_frame.pack(fill="x", padx=16, pady=8)

        self.selected_id = LabeledEntry(action_frame, "Staged ID to action:", width=100)
        self.selected_id.pack(padx=16, pady=6, anchor="w")

        self.reject_reason = LabeledEntry(action_frame, "Rejection reason:", width=240)
        self.reject_reason.pack(padx=16, pady=6, anchor="w")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=8)
        ctk.CTkButton(
            btn_row, text="✅  Approve", command=self._approve,
            fg_color=SUCCESS, hover_color="#27ae60", width=130,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            btn_row, text="❌  Reject", command=self._reject,
            fg_color=DANGER, hover_color="#c0392b", width=130,
        ).pack(side="left", padx=8)

        self._staged_rows: List[dict] = []

    def _load(self):
        from data_entry import _list_staged_scores
        self._staged_rows = _list_staged_scores("pending")
        rows = [
            (
                s["id"], s["archer_name"], s["round_name"],
                s["equipment"], str(s["date_shot"])[:10],
                "Yes" if s.get("is_competition") else "-",
            )
            for s in self._staged_rows
        ]
        self.staged_table.populate(rows)

    def _approve(self):
        from data_entry import _approve_staged
        try:
            sid = int(self.selected_id.value)
        except ValueError:
            show_error("Input", "Enter a valid staged ID."); return
        if ask_yes_no("Approve", f"Approve staged score {sid}?"):
            ok = _approve_staged(sid)
            if ok:
                show_info("Approved", f"Score {sid} approved and saved.")
                self._load()

    def _reject(self):
        from data_entry import _reject_staged
        try:
            sid = int(self.selected_id.value)
        except ValueError:
            show_error("Input", "Enter a valid staged ID."); return
        reason = self.reject_reason.value or "Rejected by recorder"
        if ask_yes_no("Reject", f"Reject staged score {sid}?"):
            _reject_staged(sid, reason)
            show_info("Rejected", f"Score {sid} marked as rejected.")
            self._load()


class DataEntryFrame(ctk.CTkFrame):
    """6 — Data entry hub with archer vs recorder sub-tabs."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text="🏹  Data Entry", font=FONT_TITLE).pack(pady=(20, 10))

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=20, pady=10)

        # Archer self-entry
        archer_tab = tabs.add("Archer Self-Entry")
        sub_a = ctk.CTkTabview(archer_tab)
        sub_a.pack(fill="both", expand=True)
        StageScoreFrame(sub_a.add("Stage a Score")).pack(fill="both", expand=True)

        # Recorder entry
        recorder_tab = tabs.add("Recorder")
        sub_r = ctk.CTkTabview(recorder_tab)
        sub_r.pack(fill="both", expand=True)
        AddArcherFrame(sub_r.add("Add Archer")).pack(fill="both", expand=True)
        AddRoundFrame(sub_r.add("Add Round")).pack(fill="both", expand=True)
        AddCompetitionFrame(sub_r.add("Add Competition")).pack(fill="both", expand=True)
        DirectScoreEntry(sub_r.add("Direct Score Entry")).pack(fill="both", expand=True)
        ApproveStagedFrame(sub_r.add("Approve Staged")).pack(fill="both", expand=True)


# ===========================================================================
# Main application window
# ===========================================================================

class ArcheryApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("🏹  Archery Score Recording System")
        self.geometry("1100x750")
        self.minsize(900, 600)

        # Sidebar + content layout
        self._build_layout()

    def _build_layout(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color="#1a1a2e")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(
            self.sidebar, text="🏹 Archery\nScoring",
            font=("Helvetica", 17, "bold"), justify="center",
        ).pack(pady=(28, 20))

        self._nav_buttons: dict[str, ctk.CTkButton] = {}

        nav_items = [
            ("1  Seed Database",      "seed"),
            ("2  Archer Lookup",      "archers"),
            ("3  Round Lookup",       "rounds"),
            ("4  Competitions",       "competitions"),
            ("5  Club Records",       "records"),
            ("6  Data Entry",         "data_entry"),
        ]
        for label, key in nav_items:
            btn = ctk.CTkButton(
                self.sidebar, text=label, anchor="w",
                fg_color="transparent", hover_color="#16213e",
                font=FONT_BODY, height=42,
                command=lambda k=key: self._show_section(k),
            )
            btn.pack(fill="x", padx=10, pady=3)
            self._nav_buttons[key] = btn

        # Version label at bottom
        ctk.CTkLabel(
            self.sidebar, text="CustomTkinter GUI\nv1.0", font=("Helvetica", 10),
            text_color="#888",
        ).pack(side="bottom", pady=16)

        # Content area
        self.content = ctk.CTkFrame(self, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

        # Build all section frames (hidden initially)
        self._sections: dict[str, ctk.CTkFrame] = {
            "seed":         SeedFrame(self.content),
            "archers":      ArcherLookupFrame(self.content),
            "rounds":       RoundLookupFrame(self.content),
            "competitions": CompetitionFrame(self.content),
            "records":      ClubRecordsFrame(self.content),
            "data_entry":   DataEntryFrame(self.content),
        }

        self._current = None
        self._show_section("seed")

    def _show_section(self, key: str):
        if self._current:
            self._sections[self._current].pack_forget()
            self._nav_buttons[self._current].configure(fg_color="transparent")

        self._sections[key].pack(fill="both", expand=True)
        self._nav_buttons[key].configure(fg_color=ACCENT)
        self._current = key


# ===========================================================================
# Entry point
# ===========================================================================

def main():
    init_db()
    app = ArcheryApp()
    app.mainloop()


if __name__ == "__main__":
    main()