"""
Flask app — one page (templates/index.html) that drives itself through the
study steps with JS, talking to these JSON API routes. All actual state
lives in SQLite (db.py); nothing here is trusted from the client except
where explicitly noted.
"""

import csv
import io
import os
import secrets
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()  # must run before `import config` — config.py reads env vars at import time

from flask import Flask, jsonify, render_template, request, Response
from openai import OpenAI

import db
import config
from randomization import assign_condition

app = Flask(__name__)

# No db.init_db() call here at import time — see the comment above
# get_db() in db.py for why. Schema creation happens lazily on first use.

ADMIN_EXPORT_PASSWORD = os.environ.get("ADMIN_EXPORT_PASSWORD")

# Switched from OpenRouter to Gemini's free tier — OpenRouter has no
# durable free tier (a negative account balance blocked every request
# mid-pilot). Google's Gemini API has an actual free tier, and exposes an
# OpenAI-compatible endpoint, so this still goes through the same openai
# package's client, just pointed at Google's base_url with a Gemini model
# name and a Gemini API key instead of an OpenRouter one.
#
# I could not verify the exact current default model name against live
# docs when writing this (no working web access at the time) — if
# AI_MODEL's default below 404s or errors on model-not-found, check
# https://ai.google.dev/gemini-api/docs/models for the current model list
# and set AI_MODEL in your .env / Render env vars to the right one. The
# rest of the integration (endpoint shape, auth) should be stable even if
# the specific model name has moved on.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
AI_MODEL = os.environ.get("AI_MODEL", "gemini-2.0-flash")

ai_client = (
    OpenAI(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=GEMINI_API_KEY,
    )
    if GEMINI_API_KEY
    else None
)


def now():
    return datetime.now(timezone.utc).isoformat()


# --- page -----------------------------------------------------------

@app.route("/")
def index():
    src = request.args.get("src", "")
    return render_template(
        "index.html",
        recruitment_source=src,
        consent_text=config.CONSENT_TEXT,
        consent_checkbox_label=config.CONSENT_CHECKBOX_LABEL,
        minimum_age=config.MINIMUM_AGE,
        scenario_text=config.SCENARIO_TEXT,
        stance_question_pre=config.STANCE_QUESTION_PRE,
        stance_question_post=config.STANCE_QUESTION_POST,
        debrief_text=config.DEBRIEF_TEXT,
        ai_use_question=config.AI_USE_QUESTION,
        ai_use_labels=config.AI_USE_LABELS,
        tech_affinity_items=config.TECH_AFFINITY_ITEMS,
        fin_lit_questions=config.FIN_LIT_QUESTIONS,
        trust_instructions=config.TRUST_INSTRUCTIONS,
        trust_items=config.TRUST_ITEMS,
        competence_items=config.COMPETENCE_ITEMS,
        bias_items=config.BIAS_ITEMS,
        intention_items=config.INTENTION_ITEMS,
    )


# --- Step 0: consent --------------------------------------------------

@app.route("/api/consent", methods=["POST"])
def api_consent():
    data = request.get_json()
    participant_id = data["participant_id"]
    recruitment_source = data.get("recruitment_source", "")
    db.save_consent(participant_id, recruitment_source, now())
    return jsonify({"ok": True})


# --- Step 1: covariates ------------------------------------------------

@app.route("/api/covariates", methods=["POST"])
def api_covariates():
    data = request.get_json()
    db.save_covariates(
        participant_id=data["participant_id"],
        ai_use_frequency=data["ai_use_frequency"],
        tech_affinity=data["tech_affinity"],          # list of 3
        fin_lit_correct=data["fin_lit_correct"],       # list of 3 booleans
        fin_lit_self_rating=data["fin_lit_self_rating"],
        age=data["age"],
        grade_year=data["grade_year"],
    )
    return jsonify({"ok": True})


# --- Step 2 + 3: stance submission and RANDOMIZATION --------------------
#
# This is the causal backbone of the study. Read randomization.py first.
#
# Ordering matters and is deliberate: the participant_id is just an
# identifier (not participant-authored content), so reading it is fine.
# But the random draw and its write to storage happen BEFORE the request
# body's stance/rationale content is parsed and stored — so nothing about
# what the participant wrote can influence, or even be involved in, the
# assignment.

@app.route("/api/submit-stance", methods=["POST"])
def api_submit_stance():
    participant_id = request.headers.get("X-Participant-Id")

    # --- RANDOMIZATION: happens first, touches nothing else yet ---
    condition = assign_condition()
    db.log_condition(participant_id, condition, now())
    # --- end randomization ---

    data = request.get_json()  # only now do we read the participant's answer
    stance = data["stance"]
    confidence = data["confidence"]
    rationale = data["rationale"]
    word_count = len(rationale.split())
    db.save_pre_stance(participant_id, stance, confidence, rationale, word_count)

    return jsonify({"ok": True})


# --- Step 4: AI verdict (v2 — honest audit against a condition-selected
# fact-set; see config.py's comment above AI_PROMPT_TEMPLATE) -------------

def scenario_facts_for_condition(condition):
    """The random condition draw (randomization.py, via the DB) selects
    WHICH fact-set the participant's reasoning is audited against — that
    selection is the actual experimental manipulation now, since the
    model is never told what verdict to reach. Never derived from
    anything participant-authored."""
    return config.SCENARIO_FACTS_AGREE if condition == "agree" else config.SCENARIO_FACTS_DISAGREE


def build_verdict_prompt(scenario_facts, participant_reasoning):
    """Pure string-building, kept separate from the API call so it's easy
    to read/test on its own."""
    return config.AI_PROMPT_TEMPLATE.format(
        scenario_facts=scenario_facts.strip(),
        participant_reasoning=participant_reasoning,
    )


@app.route("/api/generate-verdict", methods=["POST"])
def api_generate_verdict():
    data = request.get_json()
    participant_id = data["participant_id"]

    # Read condition/rationale from storage, not from the request, so the
    # AI call always reflects what was actually recorded (and randomized)
    # rather than whatever the client happens to send.
    participant = db.get_participant(participant_id)
    if participant is None or participant["condition"] is None:
        return jsonify({"error": "no condition assigned for this participant"}), 400

    scenario_facts = scenario_facts_for_condition(participant["condition"])
    prompt = build_verdict_prompt(
        scenario_facts=scenario_facts,
        participant_reasoning=participant["pre_rationale"],
    )

    if ai_client is None:
        return jsonify({"error": "GEMINI_API_KEY not configured on the server"}), 500

    # A system-only message array (no "user" turn) worked fine against
    # OpenRouter/Claude, but Gemini's OpenAI-compat layer rejects it with
    # "GenerateContentRequest.contents is not specified" — its system role
    # maps to a separate field, not to `contents`, so `contents` ends up
    # empty with nothing else in the array. Sending everything as a single
    # "user" message works universally across providers, which matters
    # now that we're on our second provider swap.
    response = ai_client.chat.completions.create(
        model=AI_MODEL,
        max_tokens=config.AI_MAX_TOKENS,
        temperature=config.AI_TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    verdict_text = response.choices[0].message.content

    db.save_ai_verdict(participant_id, verdict_text, now())
    return jsonify({"verdict": verdict_text})


# --- Step 6: post-verdict measures ---------------------------------------

@app.route("/api/post-verdict", methods=["POST"])
def api_post_verdict():
    data = request.get_json()
    db.save_post_verdict(
        participant_id=data["participant_id"],
        stance=data["stance"],
        confidence=data["confidence"],
        rationale=data["rationale"],
        trust_items=data["trust_items"],
        competence_items=data["competence_items"],
        bias_items=data["bias_items"],
        intention_items=data["intention_items"],
    )
    return jsonify({"ok": True})


# --- Step 7: debrief feedback (optional) ----------------------------------

@app.route("/api/debrief-feedback", methods=["POST"])
def api_debrief_feedback():
    data = request.get_json()
    db.save_debrief_feedback(data["participant_id"], data.get("feedback", ""), now())
    return jsonify({"ok": True})


# --- Admin export ----------------------------------------------------------

@app.route("/admin/export")
def admin_export():
    supplied = request.args.get("password", "")
    if not ADMIN_EXPORT_PASSWORD or not secrets.compare_digest(supplied, ADMIN_EXPORT_PASSWORD):
        return "Unauthorized", 401

    rows = db.all_participants()
    columns = db.column_names()

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({col: row[col] for col in columns})

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=study_export.csv"},
    )


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5050)))
