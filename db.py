"""
Data model — one table, one row per participant, columns added as the
participant moves through the steps. SQLite, single file, zero setup.

Why one wide table instead of several linked ones: this is a fixed-length
survey (no repeating sections), so a normalized schema would just add joins
without adding correctness. One row per participant also makes the CSV
export in export.py trivial — it's the table, unmodified.
"""

import os
import sqlite3
from contextlib import contextmanager

DB_PATH = "data/study.db"

# The data/ directory is empty in the repo (its only contents are the
# git-ignored .db file), and git doesn't track empty directories — so a
# fresh checkout (e.g. Render's) has no data/ folder at all until this
# runs. Without it, sqlite3.connect() fails with "unable to open database
# file" rather than creating it.
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS participants (
    id TEXT PRIMARY KEY,               -- random UUID, generated client-side at consent
    created_at TEXT NOT NULL,          -- when the row was first created (consent time)
    recruitment_source TEXT,           -- from ?src= URL param, e.g. 'northstar', 'classmates', 'prolific'

    -- Step 0: consent
    consent_given INTEGER NOT NULL DEFAULT 0,
    consent_timestamp TEXT,

    -- Step 1: covariates
    ai_use_frequency INTEGER,          -- 1-5, "How often do you use AI tools"
    tech_affinity_1 INTEGER,           -- 1-7 Likert
    tech_affinity_2 INTEGER,
    tech_affinity_3 INTEGER,
    fin_lit_q1_correct INTEGER,        -- 0/1, objective quiz item
    fin_lit_q2_correct INTEGER,
    fin_lit_q3_correct INTEGER,
    fin_lit_self_rating INTEGER,       -- 1-7 self-rated investing knowledge
    age INTEGER,
    grade_year TEXT,                   -- free text, e.g. "11th grade"

    -- Step 2: scenario + initial stance (participant-authored content)
    pre_stance TEXT,                   -- 'yes' / 'no'
    pre_confidence INTEGER,            -- 1-7, lets you compute a WOA-style
                                        -- measure against post_confidence,
                                        -- not just stance-switch rate
    pre_rationale TEXT,
    pre_rationale_word_count INTEGER,

    -- Step 3: RANDOMIZATION — see randomization.py. Logged the instant it's
    -- drawn, before pre_stance/pre_rationale above are even read by the
    -- handler. condition_assigned_at should always be <= any timestamp
    -- below it in this table.
    condition TEXT,                    -- 'agree' / 'disagree'
    condition_assigned_at TEXT,

    -- Step 4: AI verdict
    ai_verdict_text TEXT,
    ai_verdict_generated_at TEXT,

    -- Step 6: post-verdict measures
    post_stance TEXT,
    post_confidence INTEGER,           -- 1-7
    post_rationale TEXT,

    trust_1 INTEGER, trust_2 INTEGER, trust_3 INTEGER, trust_4 INTEGER,
    trust_5 INTEGER, trust_6 INTEGER, trust_7 INTEGER, trust_8 INTEGER,
    trust_9 INTEGER, trust_10 INTEGER, trust_11 INTEGER, trust_12 INTEGER,

    competence_1 INTEGER, competence_2 INTEGER, competence_3 INTEGER,
    competence_4 INTEGER, competence_5 INTEGER,   -- item 5 optional, leave NULL if unused

    bias_1 INTEGER, bias_2 INTEGER, bias_3 INTEGER,

    intention_1 INTEGER, intention_2 INTEGER, intention_3 INTEGER,  -- item 3 optional

    -- Step 7: debrief
    debrief_feedback TEXT,
    completed_at TEXT
);
"""


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute(SCHEMA)


def column_names():
    """Used by export.py to build the CSV header from the live schema,
    so the export never drifts out of sync with the table."""
    with get_db() as conn:
        cur = conn.execute("PRAGMA table_info(participants)")
        return [row["name"] for row in cur.fetchall()]


# --- one explicit function per step ---------------------------------
# Explicit named parameters rather than a generic dict-based updater:
# a little more typing here, but no risk of a column name coming from
# unvalidated user input and no need to cross-reference a whitelist.

def save_consent(participant_id, recruitment_source, timestamp):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO participants (id, created_at, recruitment_source,
                                       consent_given, consent_timestamp)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(id) DO UPDATE SET
                consent_given = 1,
                consent_timestamp = excluded.consent_timestamp
            """,
            (participant_id, timestamp, recruitment_source, timestamp),
        )


def save_covariates(participant_id, ai_use_frequency, tech_affinity,
                     fin_lit_correct, fin_lit_self_rating, age, grade_year):
    """tech_affinity: list of 3 ints. fin_lit_correct: list of 3 bools."""
    with get_db() as conn:
        conn.execute(
            """
            UPDATE participants SET
                ai_use_frequency = ?,
                tech_affinity_1 = ?, tech_affinity_2 = ?, tech_affinity_3 = ?,
                fin_lit_q1_correct = ?, fin_lit_q2_correct = ?, fin_lit_q3_correct = ?,
                fin_lit_self_rating = ?,
                age = ?,
                grade_year = ?
            WHERE id = ?
            """,
            (
                ai_use_frequency,
                *tech_affinity,
                *[int(bool(x)) for x in fin_lit_correct],
                fin_lit_self_rating,
                age,
                grade_year,
                participant_id,
            ),
        )


def save_pre_stance(participant_id, stance, confidence, rationale, word_count):
    with get_db() as conn:
        conn.execute(
            """
            UPDATE participants SET
                pre_stance = ?, pre_confidence = ?, pre_rationale = ?, pre_rationale_word_count = ?
            WHERE id = ?
            """,
            (stance, confidence, rationale, word_count, participant_id),
        )


def log_condition(participant_id, condition, timestamp):
    """Called immediately after the random draw, before the participant's
    stance/rationale are read. See app.py's /api/submit-stance route."""
    with get_db() as conn:
        conn.execute(
            "UPDATE participants SET condition = ?, condition_assigned_at = ? WHERE id = ?",
            (condition, timestamp, participant_id),
        )


def get_participant(participant_id):
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM participants WHERE id = ?", (participant_id,))
        return cur.fetchone()


def save_ai_verdict(participant_id, verdict_text, timestamp):
    with get_db() as conn:
        conn.execute(
            "UPDATE participants SET ai_verdict_text = ?, ai_verdict_generated_at = ? WHERE id = ?",
            (verdict_text, timestamp, participant_id),
        )


def save_post_verdict(participant_id, stance, confidence, rationale,
                       trust_items, competence_items, bias_items, intention_items):
    """trust_items: list of up to 12 ints. competence_items: up to 5.
    bias_items: up to 3. intention_items: up to 3. Missing trailing optional
    items should be passed as None."""
    def pad(items, length):
        items = list(items) + [None] * (length - len(items))
        return items[:length]

    trust = pad(trust_items, 12)
    competence = pad(competence_items, 5)
    bias = pad(bias_items, 3)
    intention = pad(intention_items, 3)

    with get_db() as conn:
        conn.execute(
            """
            UPDATE participants SET
                post_stance = ?, post_confidence = ?, post_rationale = ?,
                trust_1=?, trust_2=?, trust_3=?, trust_4=?, trust_5=?, trust_6=?,
                trust_7=?, trust_8=?, trust_9=?, trust_10=?, trust_11=?, trust_12=?,
                competence_1=?, competence_2=?, competence_3=?, competence_4=?, competence_5=?,
                bias_1=?, bias_2=?, bias_3=?,
                intention_1=?, intention_2=?, intention_3=?
            WHERE id = ?
            """,
            (stance, confidence, rationale, *trust, *competence, *bias, *intention, participant_id),
        )


def save_debrief_feedback(participant_id, feedback_text, timestamp):
    with get_db() as conn:
        conn.execute(
            "UPDATE participants SET debrief_feedback = ?, completed_at = ? WHERE id = ?",
            (feedback_text, timestamp, participant_id),
        )


def all_participants():
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM participants ORDER BY created_at")
        return cur.fetchall()
