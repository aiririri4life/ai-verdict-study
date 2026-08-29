"""
RANDOMIZATION — the causal backbone of this study.

Read this file first. If this function is correct, the study's core causal
claim (condition assignment causes the outcome) is valid. If it's wrong,
nothing downstream matters.

DESIGN GUARANTEE: assign_condition() takes NO arguments. It cannot see the
participant's stance, rationale, covariates, or anything else about them,
because nothing is passed in. That's not a convention we're promising to
follow — it's enforced by the function signature. There is no variable in
this function's scope that could leak participant content into the draw
even by accident.

Call it, log the result immediately, and only THEN read/store anything the
participant wrote. See app.py's /api/submit-stance route for that ordering.
"""

import random


def assign_condition():
    """
    True 50/50 random draw between 'agree' and 'disagree'.

    Uses Python's random module (Mersenne Twister), which is independent
    draw-to-draw and not seeded from anything participant-related anywhere
    in this codebase (grep for `random.seed` — there isn't one, so it seeds
    from OS entropy at process start).

    Returns:
        'agree' or 'disagree', each with probability 0.5.
    """
    return random.choice(['agree', 'disagree'])
