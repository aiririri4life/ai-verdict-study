"""
Gunicorn config — auto-loaded from this filename, no start-command flags
needed (see `gunicorn --help`'s default for -c).

timeout: raised from gunicorn's 30s default. A cold connection to Turso
on Render's free tier (throttled CPU, and the free instance cold-boots
from scratch after every spin-down) can legitimately take longer than
30s, especially for the first request after a cold start. With the
default timeout, gunicorn was treating that as a hung worker, SIGKILLing
it mid-connection, and crash-looping the whole service. See db.py's
lazy-init comment for the other half of this fix.
"""

timeout = 120
