# Investment Reasoning Study

Flask + libSQL (SQLite-compatible) web app for the AI-verdict study.
Single-page multi-step form; see `app.py` for routes, `db.py` for the data
model, and `randomization.py` for the condition-assignment logic (read
that one first — it's the part the whole study's validity depends on, and
`test_randomization.py` has the tests proving it).

## Before running a real study

Most content in `config.py` is filled in — consent text, scenario, debrief,
covariates, and all five DV scales. A few things still need a human, not code:

- **Write `SCENARIO_FACTS_AGREE` and `SCENARIO_FACTS_DISAGREE`** in
  `config.py` — currently placeholders. As of the v2 verdict prompt, the
  AI genuinely audits the participant's reasoning against whichever
  fact-set the random condition draw selects, rather than being told what
  to conclude — so these two fact-sets ARE the experimental manipulation
  now, and curating them (truthfully — every fact must trace back to
  `SCENARIO_TEXT`) is a real research-validity decision, not filler text.
  Run the blind-audit pilot described in the comment above
  `AI_PROMPT_TEMPLATE` before real participants see this.
- **Have Ben review `AI_PROMPT_TEMPLATE`** in `config.py`, and the fact-set
  curation approach above, before either touches real participants.
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
cp .env.example .env   # then edit .env with your real OPENROUTER_API_KEY
                        # and a strong ADMIN_EXPORT_PASSWORD
python app.py
```

Visit `http://localhost:5050`. Add `?src=classmates` (or whatever pool
name) to tag recruitment source, e.g. `http://localhost:5050/?src=prolific`.

Without `TURSO_DATABASE_URL` set, `data/study.db` is created automatically
on first run and is git-ignored — don't commit it, it contains response
data. This local-file mode is only for development; see the deploy section
below for why production needs Turso instead.

## Export data

```
http://localhost:5050/admin/export?password=YOUR_ADMIN_EXPORT_PASSWORD
```

Downloads everything as CSV, one row per participant, columns matching the
`participants` table in `db.py`.

## Storage: why Turso, not just a local file

Render's free tier (and most free hosts) has no persistent disk — local
files get wiped on every redeploy *and* on spin-down after ~15 minutes of
inactivity. That silently lost real participant data before this was
fixed: two test runs a redeploy apart ended up with only one row in the
export. `db.py` now connects directly to a remote
[Turso](https://turso.tech) database (SQLite-compatible, free tier, no
local file at all) whenever `TURSO_DATABASE_URL` is set, so every write
lands somewhere durable immediately instead of on Render's disk. Without
that env var set, it falls back to a local file — fine for development,
not for a real data-collection run.

To set up Turso: create a free account and a database at
[turso.tech](https://turso.tech), then grab the database URL (starts with
`libsql://`) and generate an auth token from its dashboard — both go in
your `.env` locally and in Render's environment variables for production.

## Deploy free (Render)

1. Push this repo to GitHub (data/ and .env are already git-ignored).
2. On [render.com](https://render.com), New → Web Service → connect the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variables in the Render dashboard: `OPENROUTER_API_KEY`,
   `ADMIN_EXPORT_PASSWORD`, `CONTACT_EMAIL`, `TURSO_DATABASE_URL`,
   `TURSO_AUTH_TOKEN`. Optionally `AI_MODEL` if you want a different
   OpenRouter model slug than the default in `app.py`. (`CONTACT_EMAIL`
   isn't secret, but it's set via env var rather than hardcoded in
   `config.py` since that file is in a public repo.)
6. Without `TURSO_DATABASE_URL` set, the app still runs, but every
   redeploy or spin-down wipes all collected data — see the storage
   section above. Set it before collecting anything you care about.

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
