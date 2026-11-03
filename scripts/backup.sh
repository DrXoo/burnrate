#!/usr/bin/env bash
#
# Copy the owner's financial history, and the two secrets that make it usable.
#
# A pg_dump on its own does not restore a working product: `.env` holds
# BANK_TOKEN_ENCRYPTION_KEY (without it every stored bank token is unreadable
# ciphertext) and AUTH_SECRET_KEY (without it nobody can log in), and
# secrets/enable-banking.pem signs every request to the bank, so without it the
# product cannot even re-authorize. All three are in .gitignore and exist only on
# this host, so all three go in the set.
#
# This writes to this host only. That protects against a bad migration, a wrong
# DELETE, a dropped table and Postgres corruption. It does not protect against
# losing the host; a destination off it is the upgrade, and the only line that
# changes is BURNRATE_BACKUP_DIR.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

BACKUP_DIR="${BURNRATE_BACKUP_DIR:-${HOME}/burnrate-backups}"
RETENTION="${BURNRATE_BACKUP_RETENTION:-14}"

POSTGRES_USER="$(env_value POSTGRES_USER)"
POSTGRES_DB="$(env_value POSTGRES_DB)"

# Millisecond precision so two runs in the same second cannot collide, and the
# name still sorts lexicographically, which is what retention prunes by.
stamp="$(date -u +%Y-%m-%dT%H%M%S.%3NZ)"
set_dir="${BACKUP_DIR}/${stamp}"

mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"
mkdir -m 700 "${set_dir}"

# A partial set is worse than none: it looks like a backup and is not one.
trap 'rm -rf "${set_dir}"' ERR

dump="${set_dir}/burnrate.dump"
compose exec -T postgres pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc >"${dump}"

# Verified at write time. Keeping a dump nobody has read turns a known gap into a
# false belief, which is the whole failure mode of this phase.
if ! compose exec -T postgres pg_restore --list <"${dump}" >/dev/null 2>&1; then
  echo "the dump just written is not readable by pg_restore; refusing to keep it" >&2
  exit 1
fi

cp "${REPO_ROOT}/.env" "${set_dir}/env"
cp "${REPO_ROOT}/secrets/enable-banking.pem" "${set_dir}/enable-banking.pem"
chmod 600 "${set_dir}/env" "${set_dir}/enable-banking.pem" "${dump}"

revision="$(psql_in "${POSTGRES_DB}" -t -A -c 'select version_num from alembic_version')"

{
  echo "backed_up_at=${stamp}"
  echo "database=${POSTGRES_DB}"
  echo "alembic_revision=${revision}"
  echo "dump_bytes=$(stat -c %s "${dump}")"
  echo "[rows]"
  row_counts "${POSTGRES_DB}"
} >"${set_dir}/manifest.txt"

trap - ERR

# Count-based rather than age-based: a long gap in runs must not prune away the
# only sets that survived it.
mapfile -t existing < <(find "${BACKUP_DIR}" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' | sort)
surplus=$(( ${#existing[@]} - RETENTION ))
if (( surplus > 0 )); then
  for name in "${existing[@]:0:surplus}"; do
    rm -rf "${BACKUP_DIR:?}/${name}"
  done
fi

echo "backup set written to ${set_dir}"
