"""
Tests for randomization.py — run this yourself and read the assertions,
don't just trust that it passes. This is the part of the study that has to
be right.

Run with:  python test_randomization.py
"""

import inspect
import random

from randomization import assign_condition


def test_takes_no_arguments():
    """
    The strongest guarantee against bias: if the function has zero
    parameters, it is *structurally impossible* for it to use the
    participant's stance/rationale to influence the draw, because that
    data was never passed to it.
    """
    sig = inspect.signature(assign_condition)
    assert len(sig.parameters) == 0, (
        f"assign_condition takes arguments {list(sig.parameters)} — "
        "it must take none, or it could theoretically use participant "
        "data to bias the draw."
    )
    print("PASS: assign_condition() takes no arguments.")


def test_only_returns_valid_conditions():
    for _ in range(1000):
        result = assign_condition()
        assert result in ("agree", "disagree"), f"Unexpected value: {result}"
    print("PASS: 1000 draws all returned 'agree' or 'disagree'.")


def test_roughly_fifty_fifty():
    """
    Not a proof of fairness (no finite test is), but with n=20,000 draws
    from a true 50/50 coin, the count of 'agree' should fall within
    roughly +/- 3 standard deviations of 10,000 essentially always.
    std dev = sqrt(n * p * (1-p)) = sqrt(20000 * 0.25) ~= 70.7
    So we expect 10000 +/- ~350 with extremely high probability.
    """
    n = 20000
    agree_count = sum(1 for _ in range(n) if assign_condition() == "agree")
    expected = n / 2
    tolerance = 500  # generous margin above, well beyond 3 std devs
    diff = abs(agree_count - expected)
    assert diff < tolerance, (
        f"'agree' count was {agree_count}/{n}, expected close to {expected}. "
        f"Deviation of {diff} is suspiciously large for a fair coin."
    )
    print(f"PASS: {agree_count}/{n} draws were 'agree' (expected ~{int(expected)}).")


def test_no_seed_correlation_with_participant_like_data():
    """
    Simulates the real usage pattern: for a batch of "participants" with
    very different (fake) stance/rationale content, draw a condition for
    each and confirm the *sequence* of draws looks like independent coin
    flips, not something correlated with the fake input order/content.

    This can't prove independence (nothing statistical can), but it
    exercises the actual call pattern used in app.py and checks there's
    no accidental state leaking between calls (e.g. a shared counter or
    an accidentally-fixed seed).
    """
    fake_participants = [
        {"stance": "yes" if i % 2 == 0 else "no", "rationale": f"reason #{i}"}
        for i in range(2000)
    ]
    draws = []
    for _p in fake_participants:
        # NOTE: assign_condition() is called with no reference to `_p` at
        # all — this loop mirrors app.py exactly.
        draws.append(assign_condition())

    agree_count = draws.count("agree")
    assert 800 < agree_count < 1200, f"Unexpected split: {agree_count}/2000 agree"

    # Check runs aren't suspiciously long (a sign of a broken/sticky RNG).
    longest_run = 1
    current_run = 1
    for i in range(1, len(draws)):
        if draws[i] == draws[i - 1]:
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 1
    # For 2000 fair coin flips, a run of 20+ identical results in a row
    # would be extraordinarily unlikely (~1 in 2^19 per starting position).
    assert longest_run < 20, f"Suspiciously long run of {longest_run} identical draws"

    print(
        f"PASS: 2000 draws against fake participant data — "
        f"{agree_count} agree, longest identical run = {longest_run}."
    )


def test_not_seeded_deterministically():
    """
    Confirms random.seed() hasn't been (and isn't being) called anywhere
    that would make draws predictable/reproducible. If it were, two
    independent Python processes would produce the identical sequence.
    We approximate that check within one process by reseeding from OS
    entropy mid-test and confirming the next sequence differs from a
    fixed-seed replay.
    """
    random.seed(12345)
    seeded_sequence = [assign_condition() for _ in range(50)]

    random.seed()  # reseed from OS entropy, as happens at real process start
    fresh_sequence = [assign_condition() for _ in range(50)]

    assert seeded_sequence != fresh_sequence, (
        "Sequences matched after reseeding — something is fixing the seed."
    )
    print("PASS: draws are not deterministically seeded.")


if __name__ == "__main__":
    test_takes_no_arguments()
    test_only_returns_valid_conditions()
    test_roughly_fifty_fifty()
    test_no_seed_correlation_with_participant_like_data()
    test_not_seeded_deterministically()
    print("\nAll randomization tests passed.")
