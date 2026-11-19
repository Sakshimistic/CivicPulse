"""
Run every SQL file in database/queries/ against the warehouse, print a preview and
save each result as CSV in data/interim/sql_results/.

Run from the civicpulse folder:
    python database/run_queries.py
Connection settings come from .env (see .env.example), same as load_postgres.py.
"""
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

QUERY_DIR = Path("database/queries")
OUT_DIR = Path("data/interim/sql_results")


def find_psql():
    import shutil
    found = shutil.which("psql")
    if found:
        return found
    for path in sorted(Path("C:/Program Files/PostgreSQL").glob("*/bin/psql.exe"), reverse=True):
        return str(path)
    sys.exit("psql not found.")


def main():
    if not os.getenv("PGPASSWORD"):
        sys.exit("PGPASSWORD is not set. Copy .env.example to .env and fill it in.")
    env = os.environ.copy()
    env.setdefault("PGHOST", "localhost")
    env.setdefault("PGPORT", "5432")
    env.setdefault("PGUSER", "postgres")
    db = os.getenv("PGDATABASE", "civicpulse")
    psql = find_psql()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for sql_file in sorted(QUERY_DIR.glob("*.sql")):
        csv_path = OUT_DIR / f"{sql_file.stem}.csv"
        run = lambda extra: subprocess.run(
            [psql, "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", db, "-f", str(sql_file), *extra],
            env=env, capture_output=True, text=True, encoding="utf-8")
        csv_result = run(["--csv"])
        if csv_result.returncode != 0:
            sys.exit(f"{sql_file.name} failed:\n{csv_result.stderr}")
        csv_path.write_text(csv_result.stdout, encoding="utf-8")
        print(f"\n=== {sql_file.name} ({max(csv_result.stdout.count(chr(10)) - 1, 0)} rows) ===")
        print(run([]).stdout)


if __name__ == "__main__":
    main()
