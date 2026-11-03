#!/usr/bin/env bash
#
# Is this dump readable?
#
# Usage: scripts/verify-dump.sh <dump-file>
#
# Called by backup.sh the moment a dump is written, and useful on its own against a
# set that has been sitting on disk for months: a dump nobody has read is not a
# backup, it is a belief about one.
#
# Reads the archive's table of contents only. It never connects to a database and
# never writes anything, so it is safe to run against any set at any time.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

dump="${1:-}"
if [[ -z "${dump}" ]]; then
  echo "usage: $0 <dump-file>" >&2
  exit 2
fi

if [[ ! -f "${dump}" ]]; then
  echo "no such dump: ${dump}" >&2
  exit 1
fi

# Asked separately, and first, because every way of reaching pg_restore -- Docker not
# running, the stack down, the container renamed -- exits non-zero just like a corrupt
# archive does. Reported as one, this script would tell the owner that an intact dump
# was unreadable, in exactly the situation it advertises itself for. "Not checked" and
# "unreadable" are different answers and get different exit codes.
if ! reach="$(compose exec -T postgres pg_restore --version 2>&1 >/dev/null)"; then
  echo "cannot reach pg_restore in the postgres container, so ${dump} was NOT checked:" >&2
  printf '%s\n' "${reach}" >&2
  exit 3
fi

if ! complaint="$(compose exec -T postgres pg_restore --list <"${dump}" 2>&1 >/dev/null)"; then
  echo "pg_restore cannot read ${dump}:" >&2
  printf '%s\n' "${complaint}" >&2
  exit 1
fi

echo "readable: ${dump}"
