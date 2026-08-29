# Investment Reasoning Study

Flask + SQLite web app for the AI-verdict study. Single-page multi-step
form; see `app.py` for routes, `db.py` for the data model, and
`randomization.py` for the condition-assignment logic (read that one first
— it's the part the whole study's validity depends on, and
`test_randomization.py` has the tests proving it).

## Before running a real study

All content in `config.py` is filled in — consent text, scenario, debrief,
covariates, and all five DV scales. Two things still need a human, not code:

- **Have Ben review `AI_PROMPT_TEMPLATE`** in `config.py` before it touches
  real participants — it's the piece with the most room for tone to go
  wrong (see the comment above it).
- **Flag the minors / parental-consent question to Ben.** The consent
  checkbox gates on self-attested age 13+ (enforced again numerically in
  Step 1 — see `MINIMUM_AGE` in `config.py`), which is reasonable for
  classmates recruited under normal school-context norms, but if your
  recruitment pool goes beyond that (e.g. `?src=prolific` or any public
  link), that self-attestation is probably not enough on its own — this is
  an IRB-style judgment call for an advisor, not something to default your
  way through in code.

## Analysis reference: DV → hypothesis mapping

For your write-up, not enforced anywhere in code:

| Hypothesis | Primary DV(s) |
|---|---|
| H1 (sycophancy trap — trust tracks agreement, not correctness) | DV1 (Trust) |
| H2 (grounding buys trust back) | Out of scope for this two-cell (agree/disagree only) version — would need a third bare-vs-evidence factor. Say so explicitly in the write-up rather than dropping it silently. |
| H3 (bias blind spot) | DV4 (Perceived bias) |
| Exploratory: does disagreement reduce advice-uptake | DV3 — stance-switch rate (`pre_stance` vs. `post_stance`) and confidence delta (`pre_confidence` vs. `post_confidence`), broken out by `condition`. Not asked directly — compute from the CSV export. |
| Exploratory: disagreement → perceived competence, independent of trust | DV2 |
| Exploratory: downstream behavioral intent | DV5 |
| Moderator check | Covariates (financial literacy, prior AI use, tech affinity) as moderators of condition → trust |

Scoring notes live as comments right above `TRUST_ITEMS` and `BIAS_ITEMS`
in `config.py` (which items are reverse-scored, which item to
report/analyze separately).

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env with your real ANTHROPIC_API_KEY
                        # and a strong ADMIN_EXPORT_PASSWORD
python app.py
```

Visit `http://localhost:5050`. Add `?src=classmates` (or whatever pool
name) to tag recruitment source, e.g. `http://localhost:5050/?src=prolific`.

`data/study.db` is created automatically on first run and is
git-ignored — don't commit it, it contains response data.

## Export data

```
http://localhost:5050/admin/export?password=YOUR_ADMIN_EXPORT_PASSWORD
```

Downloads everything as CSV, one row per participant, columns matching the
`participants` table in `db.py`.

## Deploy free (Render)

1. Push this repo to GitHub (data/ and .env are already git-ignored).
2. On [render.com](https://render.com), New → Web Service → connect the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variables in the Render dashboard: `ANTHROPIC_API_KEY`,
   `ADMIN_EXPORT_PASSWORD`, `CONTACT_EMAIL`. (`CONTACT_EMAIL` isn't secret,
   but it's set via env var rather than hardcoded in `config.py` since
   that file is in a public repo.)
6. Render's free tier disk is ephemeral — the SQLite file will reset on
   redeploys/restarts. For a real data-collection run, either upgrade to a
   Render disk (small paid add-on) or periodically hit `/admin/export` and
   save the CSV somewhere durable as you collect responses.

## Notes on the design

- **Randomization** happens server-side in `/api/submit-stance`
  (`app.py`), calling `assign_condition()` (`randomization.py`) *before*
  the request body — the participant's actual stance/rationale — is even
  parsed. The condition and its timestamp are written to the DB
  immediately, in that same request, before anything participant-authored
  is stored.
- **No PII**: participant IDs are random UUIDs generated in the browser
  (`static/js/app.js`) and never tied to a name/email. The server doesn't
  log IPs beyond Flask/Render's normal access logs.
- **Duplicate prevention**: a `localStorage` flag set only after the
  debrief step blocks re-entry from the same browser. It's not
  bulletproof (clearing storage or using another browser bypasses it) but
  matches the "simple" bar from the spec.
