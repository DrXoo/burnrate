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
# -E matters here and is not decoration: without errtrace the ERR trap below is not
# reached when the failure happens inside a function, and every command that can fail
# in this script runs through one. A backup that failed then left its partial set on
# disk looking like a backup.
set -Eeuo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

BACKUP_DIR="${BURNRATE_BACKUP_DIR:-${HOME}/burnrate-backups}"
RETENTION="${BURNRATE_BACKUP_RETENTION:-14}"

if [[ ! "${RETENTION}" =~ ^[0-9]+$ ]] || (( RETENTION < 1 )); then
  echo "BURNRATE_BACKUP_RETENTION must be a whole number of sets, at least 1." >&2
  echo "A retention of 0 would prune away the set this run is about to write." >&2
  exit 2
fi

POSTGRES_USER="$(env_value POSTGRES_USER)"
# env_file_value: the database worth backing up is the one the stack runs on, which is
# what .env says and not what this process happened to inherit.
POSTGRES_DB="$(env_file_value POSTGRES_DB)"

# Millisecond precision so two runs in the same second cannot collide, and the
# name still sorts lexicographically, which is what retention prunes by.
stamp="$(date -u +%Y-%m-%dT%H%M%S.%3NZ)"
set_dir="${BACKUP_DIR}/${stamp}"

# Retention matches this and nothing else. Anything else kept in the backup directory
# -- a note, a set copied off another host, the log file's directory -- then neither
# occupies a retention slot nor gets deleted by a tool the owner pointed at backups.
SET_GLOB='[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T*Z'

mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"
mkdir -m 700 "${set_dir}"

# A partial set is worse than none: it looks like a backup and is not one.
#
# The exit is not decoration either. A trap that only deletes hands control back to the
# line after the one that was interrupted, so a run killed during the manifest would
# remove its set, carry on, and finish by printing "backup set written to ..." and
# exiting 0 -- the exact false belief the cleanup exists to prevent.
cleanup() {
  local status=$?
  trap - ERR INT TERM EXIT
  rm -rf "${set_dir}"
  (( status != 0 )) || status=1
  exit "${status}"
}
# EXIT is in the list because `exit 1` is not an error as far as an ERR trap is
# concerned, and one of the paths below exits deliberately.
trap cleanup ERR INT TERM EXIT

dump="${set_dir}/burnrate.dump"

# The manifest has to describe the dump, not the database a moment after it. The sync
# worker commits a sync_sessions row every thirty minutes, so a count taken afterwards
# can disagree with the dump, and the restore check would then report a loss that never
# happened -- a check that cries wolf is a check nobody reads.
#
# Counting either side and insisting the two agree is the cheap form of that guarantee.
# The exact form is to share pg_dump's own snapshot, which means holding a transaction
# open from bash across the longest step in the script; a backup script is the wrong
# place to be clever, and the cheap form is honest about when it does not know. A
# disagreement retries once, because a collision is rare and passes, and then fails
# rather than writing a manifest it cannot stand behind.
counted_rows=""
for attempt in 1 2; do
  before="$(row_counts "${POSTGRES_DB}")"
  compose exec -T postgres pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc >"${dump}"
  counted_rows="$(row_counts "${POSTGRES_DB}")"
  [[ "${before}" != "${counted_rows}" ]] || break
  if (( attempt == 2 )); then
    echo "the database changed during both dump attempts, so no manifest describes them" >&2
    exit 1
  fi
done

# Verified at write time. Keeping a dump nobody has read turns a known gap into a
# false belief, which is the whole failure mode of this phase. The cleanup trap above
# is what removes the set, so a dump that fails here is never left behind.
"${REPO_ROOT}/scripts/verify-dump.sh" "${dump}" >/dev/null

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
  # The counts agreed across the dump above. Asking a third time would be a third
  # answer, and the one thing this file must not do is disagree with the dump.
  printf '%s\n' "${counted_rows}"
} >"${set_dir}/manifest.txt"

trap - ERR INT TERM EXIT

# Count-based rather than age-based: a long gap in runs must not prune away the
# only sets that survived it.
mapfile -t existing < <(find "${BACKUP_DIR}" -maxdepth 1 -mindepth 1 -type d -name "${SET_GLOB}" -printf '%f\n' | sort)
surplus=$(( ${#existing[@]} - RETENTION ))
if (( surplus > 0 )); then
  for name in "${existing[@]:0:surplus}"; do
    rm -rf "${BACKUP_DIR:?}/${name}"
  done
fi

echo "backup set written to ${set_dir}"
