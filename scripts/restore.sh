#!/usr/bin/env bash
#
# Restore a backup set into a database.
#
# Usage: scripts/restore.sh <backup-set-dir> --database NAME [--allow-live]
#
# Restoring is destructive, so the live database is refused unless it is named
# deliberately: a recovery tool that can be pointed at production by a slip of the
# shell is itself a way to lose the data.
#
# The database is only part of a recovery. The set's `env` and `enable-banking.pem`
# have to be put back by hand -- see the restore procedure in README.md -- because
# without BANK_TOKEN_ENCRYPTION_KEY the restored bank tokens are unreadable
# ciphertext and without the signing key the product cannot call the bank at all.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

usage() {
  echo "usage: $0 <backup-set-dir> --database NAME [--allow-live]" >&2
  exit 2
}

set_dir=""
target=""
allow_live="no"

while (( $# )); do
  case "$1" in
    --database) target="${2:-}"; shift 2 ;;
    --allow-live) allow_live="yes"; shift ;;
    -h|--help) usage ;;
    *) [[ -z "${set_dir}" ]] || usage; set_dir="$1"; shift ;;
  esac
done

[[ -n "${set_dir}" && -n "${target}" ]] || usage

dump="${set_dir}/burnrate.dump"
[[ -f "${dump}" ]] || { echo "no dump at ${dump}" >&2; exit 1; }

POSTGRES_USER="$(env_value POSTGRES_USER)"
POSTGRES_DB="$(env_value POSTGRES_DB)"

if [[ "${target}" == "${POSTGRES_DB}" && "${allow_live}" != "yes" ]]; then
  cat >&2 <<MSG
refusing to restore over the live database "${target}".
Pass --allow-live if that is genuinely what you want; restoring is destructive and
overwrites everything the stack is using right now.
MSG
  exit 1
fi

exists="$(psql_in postgres -t -A -c "select 1 from pg_database where datname = '${target}'")"
if [[ -z "${exists}" ]]; then
  psql_in postgres -c "CREATE DATABASE \"${target}\"" >/dev/null
fi

compose exec -T postgres pg_restore \
  -U "${POSTGRES_USER}" -d "${target}" \
  --clean --if-exists --no-owner --no-privileges --exit-on-error <"${dump}"

echo "restored into ${target}:"
row_counts "${target}"
