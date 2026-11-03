# Shared by backup.sh and restore.sh. Not executable on its own.
#
# The row-count query lives here and nowhere else. Backup writes the counts and
# restore reads them back, so two spellings of "how many rows are there" would make
# the comparison meaningless -- the same defect `burnrate.db.budget_windows` and
# `burnrate.db.counted_spend` both exist to prevent.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

env_value() {
  local key="$1"
  local line
  line="$(grep -m1 "^${key}=" "${REPO_ROOT}/.env" || true)"
  if [[ -z "${line}" ]]; then
    echo "${key} is not set in ${REPO_ROOT}/.env" >&2
    return 1
  fi
  printf '%s' "${line#*=}"
}

# Exact counts, not pg_stat estimates: this is checked against a restore.
ROW_COUNT_SQL="
select table_name,
       (xpath('/row/cnt/text()', query_to_xml(format('select count(*) as cnt from %I.%I', table_schema, table_name), false, true, '')))[1]::text::bigint
from information_schema.tables
where table_schema = 'public' and table_type = 'BASE TABLE' and table_name <> 'alembic_version'
order by table_name;
"

compose() {
  (cd "${REPO_ROOT}" && docker compose "$@")
}

psql_in() {
  local database="$1"
  shift
  compose exec -T postgres psql -U "${POSTGRES_USER}" -d "${database}" -v ON_ERROR_STOP=1 "$@"
}

row_counts() {
  psql_in "$1" -t -A -F= -c "${ROW_COUNT_SQL}"
}
