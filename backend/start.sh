#!/bin/sh
# Container entrypoint for the DigitalOcean backend service.
#
# DO App Platform runs `run_command` via shlex split (NOT a shell), so a
# "python init_db && uvicorn" one-liner silently passes `&&` as argv to python
# and uvicorn never starts. This script gives us a real shell: build the schema
# (idempotent) then hand off to uvicorn as PID 1 via exec (clean signals).
set -e

python scripts/init_db.py
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
