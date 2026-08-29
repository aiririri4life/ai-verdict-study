"""
Study content — the text participants actually see, and the AI prompt
template. Kept here as constants (not hardcoded in HTML/JS) so you can
edit wording without touching app logic.

REPLACE THE PLACEHOLDER TEXT BELOW with your real consent form, scenario,
and debrief text before running a real study.
"""

import os

# --- contact email, used in both consent and debrief text below ---------
# Read from the environment (like ANTHROPIC_API_KEY / ADMIN_EXPORT_PASSWORD)
# rather than hardcoded here, since this file is committed to a public
# repo — set the real value in .env locally and in Render's dashboard.
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "[CONTACT_EMAIL not set]")

# --- Step 0: consent screen -------------------------------------------
CONSENT_TEXT = f"""About this study

Thank you for considering taking part in this research study, conducted independently by a high school student (Ria Singh) as part of an investigation into how people respond to AI-generated feedback on their reasoning.

What you'll do: You'll read a short, hypothetical investment scenario, state whether you'd make the investment and explain your reasoning, then receive a response from an AI tool. Afterward, you'll answer some questions about your reaction to that response and restate your decision. The whole thing takes about 8–10 minutes.

What's being studied: This study is not evaluating you, your intelligence, or the quality of your investment reasoning. It is studying how people's trust in an AI system is affected by whether that system agrees or disagrees with them. Full details will be shared with you after you complete the study, since knowing them in advance would affect the results.

Your data: Your responses are anonymous — we do not collect your name or contact information. A random ID is assigned to your responses for research purposes only. Data will be used for a student research project and may be shared publicly in aggregate, anonymized form (e.g., in a write-up or presentation); no individual's identity will ever be connected to their responses.

Risks: This study involves a hypothetical scenario, not real money or real decisions, so there is no financial risk. Some participants may find AI feedback that disagrees with their reasoning mildly uncomfortable; there is no other anticipated risk.

Your rights: Participation is completely voluntary. You may stop at any point without penalty, and you may skip any question you're not comfortable answering. There is no compensation for participating.

Questions: If you have questions about this study, you can contact Ria Singh at {CONTACT_EMAIL}. This study is being advised by Ben Charoenwong (INSEAD)."""

# Checkbox label shown next to the consent checkbox on Step 0 — combines
# the age attestation with agreement to participate, matching CONSENT_TEXT.
CONSENT_CHECKBOX_LABEL = (
    "I am 13 years of age or older, I have read the above, "
    "and I agree to participate."
)

# Minimum age enforced against the numeric age entered in Step 1
# covariates, to back up the checkbox attestation above with an actual
# check. If you raise/lower the age line in CONSENT_TEXT and the checkbox
# label, update this to match.
MINIMUM_AGE = 13

# --- Step 2: the fixed investment scenario -----------------------------
SCENARIO_TEXT = """TechFlow Inc. is a mid-sized software company. Over the past year, its stock price has risen 40%, driven mainly by strong revenue growth. A closer look shows that TechFlow's revenue growth has come almost entirely from one large government contract signed 8 months ago, which accounts for 35% of total revenue this year. The company's core subscription business (its original product line) has grown only 3% over the same period — well below the industry average of 12%. TechFlow's CEO recently stated in an earnings call that the company is "exploring additional government partnerships to build on this momentum."

You are considering investing a portion of your savings in TechFlow Inc. stock.
"""

# Stance question wording — asked twice (Step 2, before the AI verdict, and
# Step 6, after it). Templates and JS reference these two constants rather
# than hardcoding the question text, so both stay in sync with the fixed
# scenario above if you ever change the company/investment framing.
STANCE_QUESTION_PRE = "Based on this information, would you invest in TechFlow Inc.?"
STANCE_QUESTION_POST = "After seeing this analysis, would you invest in TechFlow Inc.?"

# --- Step 7: debrief screen ---------------------------------------------
# The literal token {{PARTICIPANT_ID}} below is NOT Jinja syntax — this
# string is passed into the template as plain variable content, so Jinja
# never re-parses it. static/js/app.js finds-and-replaces that exact
# token with the real participant ID client-side when Step 7 is shown,
# since the ID isn't known until the browser generates it.
WITHDRAWAL_WINDOW = "7 days"

DEBRIEF_TEXT = f"""Thank you — here's what this study was actually about.

The AI's response to your reasoning was randomly assigned before you ever wrote it — a coin flip decided, independent of anything about you or your argument, whether the AI would agree or disagree with your decision. It was not a genuine, independent assessment of the quality of your thinking, and it does not reflect on how good your reasoning actually was.

Why the deception was necessary: If you had known in advance that the AI's agreement or disagreement was random, it likely would have changed how much you trusted or engaged with its response — which would have made it impossible to measure what we're actually studying.

What we're studying: A common finding in behavioral research is that people trust AI tools more when the AI agrees with them, and less when it disagrees — even when the AI's disagreement might be the more useful, accurate signal. This matters because tools designed to catch flawed reasoning (like the one this study is modeled on) only work if people actually listen when the tool pushes back. We're testing whether that trust gap shows up here, and whether it's specific to disagreement itself rather than to the quality of the AI's reasoning.

Your data: Your responses remain anonymous and will be used only for this research. If you'd like to withdraw your data now that you know the full purpose, contact {CONTACT_EMAIL} with your participant ID (shown below) within {WITHDRAWAL_WINDOW}, and it will be deleted.

Your participant ID: {{{{PARTICIPANT_ID}}}}

Questions or concerns: {CONTACT_EMAIL}. Thank you again for your time — this study wouldn't be possible without you."""

# --- Step 4: AI verdict prompt template ---------------------------------
# {scenario}, {stance}, {rationale}, {condition} are filled in by
# build_verdict_prompt() in app.py. `condition` comes from randomization.py
# via the DB — 'agree'/'disagree' — and is upper-cased to AGREE/DISAGREE
# before being dropped into this template's INPUT section. Both branches'
# instructions live in the template text itself; only the INPUT data
# changes per participant, which is deliberate — the model is never asked
# to independently judge the reasoning, only to write in the assigned
# direction.
#
# Have Ben review this exact template before it touches real participants —
# it's the piece with the most room for tone to go wrong.
AI_PROMPT_TEMPLATE = """You are simulating the output of an investment-analysis AI tool that gives a
second opinion on a user's investment reasoning. You will be given: (1) a fixed
investment scenario, (2) a participant's Yes/No decision, (3) their stated
reasoning, and (4) an assigned "condition" — either AGREE or DISAGREE.

Your task: write a short (3-5 sentence) analytical response, in the voice of a
serious, professional investment-analysis tool, that is consistent with the
assigned condition. Reference the participant's SPECIFIC stated reasoning by
name — quote or closely paraphrase something they said — so the response feels
targeted and responsive, not generic.

If condition = AGREE: write a response that supports the participant's decision
and reasoning, citing plausible-sounding analytical support (you may reference
real elements of the scenario, e.g., the government contract or subscription
growth, framed in a way that supports their stance).

If condition = DISAGREE: write a response that respectfully but clearly contests
the participant's decision and reasoning, citing plausible-sounding analytical
concerns grounded in the scenario (e.g., revenue concentration risk, the
underperforming core business) framed in a way that challenges their stance.

IMPORTANT CONSTRAINTS:
- The response must be assigned by the pre-determined condition, NOT by your own
  independent judgment of whether their reasoning was actually good. Do not
  evaluate correctness — only produce a response matching the assigned direction.
- Keep tone analytical, respectful, and non-condescending in BOTH conditions —
  never dismissive, never harsh, even when disagreeing.
- Do not mention that this is a study, that the condition was randomly assigned,
  or break character in any way.
- Ground every claim in details actually present in the scenario — do not
  invent new facts about TechFlow not given in the prompt.
- 3-5 sentences, professional tone, no bullet points — write as flowing prose,
  as if it's a short analyst note.

INPUT:
Scenario: {scenario}
Participant's decision: {stance}
Participant's stated reasoning: "{rationale}"
Assigned condition: {condition}

Write the analyst response now.
"""

# --- Step 1: covariates ---------------------------------------------

AI_USE_QUESTION = "How often do you use AI tools such as ChatGPT, Claude, or similar?"
AI_USE_LABELS = ["Never", "Rarely", "Sometimes", "Often", "Daily"]  # 1 through 5

TECH_AFFINITY_ITEMS = [
    "I am comfortable learning to use new technology.",
    "I enjoy figuring out how new software or apps work.",
    "I feel confident using unfamiliar digital tools.",
]

# The standard "Big Three" financial literacy items (Lusardi & Mitchell):
# compound interest, risk diversification, inflation. Each has a single
# correct option index (0-based) into its own `options` list.
FIN_LIT_QUESTIONS = [
    {
        "question": (
            "Suppose you had $100 in a savings account earning 2% interest "
            "per year. After 5 years, how much would you have — more than "
            "$102, exactly $102, or less than $102?"
        ),
        "options": ["More than $102", "Exactly $102", "Less than $102"],
        "correct_index": 0,
    },
    {
        "question": (
            "True or False: Buying a single company's stock usually "
            "provides a safer return than a mutual fund."
        ),
        "options": ["True", "False"],
        "correct_index": 1,
    },
    {
        "question": (
            "If inflation is higher than the interest rate on your "
            "savings, will you be able to buy more, less, or the same "
            "amount with your savings?"
        ),
        "options": ["More", "Less", "The same"],
        "correct_index": 1,
    },
]

# --- Step 6: post-verdict scales -----------------------------------------

# DV1 — Trust in Automated Systems (Jian, Bisantz & Drury, 2000). Kept in
# the original "the system" wording (not adapted to "the AI") — that's
# deliberate per the instrument spec, for comparability with the source
# scale, even though the rest of this study's copy says "the AI"/"this AI
# tool". If that inconsistency in phrasing bothers you, it's easy to
# find-and-replace here, but it's the literal validated wording.
TRUST_INSTRUCTIONS = "Thinking about the analysis you just received, please rate your agreement with each statement."

# Scoring note for analysis: items 1-5 are the distrust subscale and are
# reverse-scored when computing a composite trust score; items 6-11 are
# the trust subscale (higher = more trust); item 12 (familiarity) is
# usually reported/analyzed separately, not folded into the trust
# composite, per the original factor analysis. Consider reporting both
# the 12-item and 11-item (dropping familiarity) composite.
TRUST_ITEMS = [
    "The system is deceptive.",                                    # 1 - reverse-scored
    "The system behaves in an underhanded manner.",                 # 2 - reverse-scored
    "I am suspicious of the system's intent, action, or outputs.",  # 3 - reverse-scored
    "I am wary of the system.",                                     # 4 - reverse-scored
    "The system's actions will have a harmful or injurious outcome.",  # 5 - reverse-scored
    "I am confident in the system.",                                # 6
    "The system provides security.",                                # 7
    "The system has integrity.",                                    # 8
    "The system is dependable.",                                    # 9
    "The system is reliable.",                                      # 10
    "I can trust the system.",                                      # 11
    "I am familiar with the system.",                               # 12 - familiarity, not part of trust composite
]

# DV2 — Perceived competence / credibility
COMPETENCE_ITEMS = [
    "This AI tool is competent at analyzing investment decisions.",
    "This AI tool's reasoning was well thought out.",
    "This AI tool is knowledgeable about investing.",
    "I would consider this AI tool credible on financial topics.",
]

# DV4 — Perceived bias. Item 2 is reverse-scored (a fairness statement,
# not a bias statement) — flip it before combining into a bias composite.
BIAS_ITEMS = [
    "This AI tool's analysis was biased.",
    "This AI tool was fair in how it evaluated my reasoning.",  # reverse-scored
    "This AI tool seemed to have an agenda rather than an objective view.",
]

# DV5 — Intention to use again
INTENTION_ITEMS = [
    "I would use this AI tool again for future investment decisions.",
    "I would recommend this AI tool to someone else.",
    "I would trust this AI tool with a more important financial decision than this one.",
]

# DV3 — Advice-taking / Weight-on-Advice is NOT asked directly; it's
# computed from pre_stance vs. post_stance (switch rate, broken out by
# condition and switch direction) and pre_confidence vs. post_confidence
# in your own analysis from the CSV export. See db.py for those columns.
