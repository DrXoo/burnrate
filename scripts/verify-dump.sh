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

if ! compose exec -T postgres pg_restore --list <"${dump}" >/dev/null 2>&1; then
  echo "pg_restore cannot read ${dump}" >&2
  exit 1
fi

echo "readable: ${dump}"
