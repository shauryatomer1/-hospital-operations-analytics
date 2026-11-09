#!/usr/bin/env python3
"""
Phase 4-6 - build the PostgreSQL database end to end.

Two ways to run (no manual DB setup needed for the first):
  1) Embedded PostgreSQL 16 (pip package `pgserver`, data kept in ./.pgdata)   ->  python load_database.py
  2) Your own PostgreSQL server                                               ->  python load_database.py --dsn postgresql://user:pwd@localhost:5432/hospital

Steps (all by default, or choose with --steps):
  schema      database/schema.sql
  load        COPY of data/processed/*.csv   (identical to database/data_import.sql, which needs the psql client)
  dq          database/data_quality_checks.sql  -> prints PASS/WARN/FAIL; aborts on a Critical FAIL
  transform   database/transformations.sql
  views       database/views.sql
  queries     database/analytical_queries.sql -> analysis/sql_results/Qnn_*.csv  + analysis/sql_results/_summary.md
"""
import argparse
import re
import sys
import time
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
LOAD_ORDER = ["departments", "patients", "doctors", "beds", "admissions", "emergency_visits",
              "doctor_activity", "readmissions"]


def connect(a):
    if a.dsn:
        return psycopg2.connect(a.dsn), None
    import pgserver
    srv = pgserver.get_server(str(Path(a.pgdata).resolve()), cleanup_mode=None)
    srv.psql("SELECT 1;")
    uri = srv.get_uri()
    # create the database if needed
    c = psycopg2.connect(uri); c.autocommit = True
    cur = c.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname='hospital'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE hospital")
    c.close()
    dsn = re.sub(r"/[^/?]*(\?|$)", r"/hospital\1", uri, count=1) if "postgresql://" in uri else uri
    return psycopg2.connect(dsn), srv


def run_file(conn, path):
    with open(path, encoding="utf-8") as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall() if cur.description else None
        cols = [d[0] for d in cur.description] if cur.description else None
    conn.commit()
    return cols, rows


def step_load(conn, data_dir):
    with conn.cursor() as cur:
        cur.execute("SET search_path = hospital, public")
        for t in LOAD_ORDER:
            with open(data_dir / f"{t}.csv", encoding="utf-8") as f:
                cur.copy_expert(f"COPY {t} FROM STDIN WITH (FORMAT csv, HEADER true)", f)
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"   loaded {t:<18} {cur.fetchone()[0]:>8,} rows")
        cur.execute("ANALYZE")
    conn.commit()


def step_dq(conn):
    cols, rows = run_file(conn, ROOT / "database" / "data_quality_checks.sql")
    crit = 0
    for r in rows:
        flag = {"PASS": "+", "WARN": "!", "FAIL": "x"}[r[5]]
        print(f"   {flag} {r[0]} {r[5]:<4} [{r[6]:<8}] {r[2]} (violations={r[4]})")
        crit += (r[5] == "FAIL")
    print(f"   -> {sum(r[5]=='PASS' for r in rows)} PASS, {sum(r[5]=='WARN' for r in rows)} WARN, {crit} FAIL (critical)")
    return crit


def split_queries(text):
    parts = re.split(r"(?m)^-- @(Q\d+)\s*\|\s*(.*)$", text)
    out = []
    for i in range(1, len(parts), 3):
        out.append((parts[i], parts[i + 1].strip(), parts[i + 2]))
    return out


def step_queries(conn, out_dir):
    import csv
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("Q*.csv"): old.unlink()
    text = (ROOT / "database" / "analytical_queries.sql").read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute("SET search_path = hospital, public")
    summary = ["# SQL execution summary", "", "| Query | Title | Rows | Seconds |", "|---|---|---|---|"]
    n_ok = 0
    for qid, title, body in split_queries(text):
        sql = body.strip().rstrip(";")
        if not sql:
            continue
        t0 = time.time()
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        dt = time.time() - t0
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:50]
        with open(out_dir / f"{qid}_{slug}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(cols); w.writerows(rows)
        summary.append(f"| {qid} | {title} | {len(rows)} | {dt:.2f} |")
        print(f"   {qid} {title[:60]:<60} rows={len(rows):<5} {dt:.2f}s")
        n_ok += 1
    (out_dir / "_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(f"   -> {n_ok} queries executed OK")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsn", help="postgresql://user:pwd@host:port/dbname  (omit to use embedded PostgreSQL)")
    ap.add_argument("--pgdata", default=str(ROOT / ".pgdata"))
    ap.add_argument("--data", default=str(ROOT / "data" / "processed"))
    ap.add_argument("--steps", default="schema,load,dq,transform,views,queries")
    a = ap.parse_args()
    steps = a.steps.split(",")
    conn, srv = connect(a)
    with conn.cursor() as cur:
        cur.execute("SELECT version()"); print("Connected:", cur.fetchone()[0][:60])
    db = ROOT / "database"
    if "schema" in steps:
        print("[1] schema.sql"); run_file(conn, db / "schema.sql"); print("   ok")
    if "load" in steps:
        print("[2] load processed CSVs"); step_load(conn, Path(a.data))
    if "dq" in steps:
        print("[3] data_quality_checks.sql")
        if step_dq(conn):
            sys.exit("Critical data-quality failure - aborting.")
    if "transform" in steps:
        print("[4] transformations.sql"); run_file(conn, db / "transformations.sql"); print("   ok")
    if "views" in steps:
        print("[5] views.sql"); run_file(conn, db / "views.sql"); print("   ok")
    if "queries" in steps:
        print("[6] analytical_queries.sql"); step_queries(conn, ROOT / "analysis" / "sql_results")
    conn.close()


if __name__ == "__main__":
    main()
