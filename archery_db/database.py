# database.py
import sqlite3
from pathlib import Path


DB_PATH = Path("archery_scores.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # enforce FK constraints
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # 1. Archers
    cur.execute("""
    CREATE TABLE IF NOT EXISTS archers (
        id              INTEGER PRIMARY KEY,
        first_name      TEXT    NOT NULL,
        last_name       TEXT    NOT NULL,
        gender          TEXT    NOT NULL,
        age_class       TEXT    NOT NULL,
        date_of_birth   DATE,
        default_equipment TEXT  NOT NULL,
        joined_date     DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    # 2. Rounds (definitional)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rounds (
        id              INTEGER PRIMARY KEY,
        name            TEXT    UNIQUE NOT NULL,
        total_arrows    INTEGER NOT NULL,
        possible_score  INTEGER NOT NULL,
        valid_from      DATE,
        valid_to        DATE
    )""")

    # 3. Round Ranges
    cur.execute("""
    CREATE TABLE IF NOT EXISTS round_ranges (
        id              INTEGER PRIMARY KEY,
        round_id        INTEGER NOT NULL,
        range_number    INTEGER NOT NULL,
        distance        INTEGER NOT NULL,
        ends            INTEGER NOT NULL,
        face_size       INTEGER NOT NULL,
        FOREIGN KEY(round_id) REFERENCES rounds(id) ON DELETE CASCADE
    )""")

    # 4. Equivalent Rounds (time-dependent; history preserved per brief)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS equivalent_rounds (
        id              INTEGER PRIMARY KEY,
        base_round_id   INTEGER NOT NULL,
        equiv_round_id  INTEGER NOT NULL,
        gender          TEXT    NOT NULL,
        age_class       TEXT    NOT NULL,
        equipment       TEXT    NOT NULL,
        valid_from      DATE,
        valid_to        DATE,
        FOREIGN KEY(base_round_id) REFERENCES rounds(id),
        FOREIGN KEY(equiv_round_id) REFERENCES rounds(id)
    )""")

    # 5. Competitions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS competitions (
        id              INTEGER PRIMARY KEY,
        name            TEXT    NOT NULL,
        date            DATE    NOT NULL,
        round_id        INTEGER,
        is_championship BOOLEAN DEFAULT 0,
        FOREIGN KEY(round_id) REFERENCES rounds(id)
    )""")

    # 6. Scores (one full round shot)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS scores (
        id              INTEGER PRIMARY KEY,
        archer_id       INTEGER NOT NULL,
        round_id        INTEGER NOT NULL,
        equipment       TEXT    NOT NULL,
        date_shot       DATETIME NOT NULL,
        is_competition  BOOLEAN DEFAULT 0,
        competition_id  INTEGER,
        total_score     INTEGER NOT NULL,
        notes           TEXT,
        FOREIGN KEY(archer_id)      REFERENCES archers(id),
        FOREIGN KEY(round_id)       REFERENCES rounds(id),
        FOREIGN KEY(competition_id) REFERENCES competitions(id)
    )""")

    # 7. Score Ends (up to 6 arrows per end)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS score_ends (
        id           INTEGER PRIMARY KEY,
        score_id     INTEGER NOT NULL,
        range_number INTEGER NOT NULL,
        end_number   INTEGER NOT NULL,
        arrow1       INTEGER,
        arrow2       INTEGER,
        arrow3       INTEGER,
        arrow4       INTEGER,
        arrow5       INTEGER,
        arrow6       INTEGER,
        FOREIGN KEY(score_id) REFERENCES scores(id) ON DELETE CASCADE
    )""")

    conn.commit()
    conn.close()
    print(" Database schema initialized successfully.")
