"""Escalation log.

Every time the bot hands a question to a human, the handoff is saved here.
A CRM, ticketing tool or live chat system can read this table later.

Commands, run from the project folder
  python src/escalations.py list
  python src/escalations.py show E-0001
  python src/escalations.py resolve E-0001 "What the human told the customer" "Category"
"""
import json
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import yaml

DB = Path("data/escalations.db")


def _connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute(
        """CREATE TABLE IF NOT EXISTS escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            question TEXT,
            reason_code TEXT,
            reason TEXT,
            top_similarity REAL,
            closest_document TEXT,
            candidate_ids TEXT,
            status TEXT DEFAULT 'new',
            resolution TEXT,
            resolved_at TEXT,
            ticket_id TEXT)"""
    )
    return con


def _ref(n):
    return f"E-{n:04d}"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def log_escalation(result):
    """Saves one handoff and returns its reference, for example E-0007."""
    h = result["handoff"]
    ids = [c["id"] for c in result.get("candidates", [])]
    with closing(_connect()) as con:
        cur = con.execute(
            """INSERT INTO escalations
               (created_at, question, reason_code, reason, top_similarity, closest_document, candidate_ids)
               VALUES (?,?,?,?,?,?,?)""",
            (
                _now(),
                h["question"],
                h["reason_code"],
                h["reason"],
                h["top_similarity"],
                h.get("closest_document"),
                json.dumps(ids),
            ),
        )
        con.commit()
        return _ref(cur.lastrowid)


# ---------- Command line ----------

def _row_number(ref):
    return int(ref.upper().replace("E-", ""))


def cmd_list():
    with closing(_connect()) as con:
        rows = con.execute("SELECT * FROM escalations ORDER BY id").fetchall()
    if not rows:
        print("No escalations yet.")
        return
    print(f"{'Ref':8s} {'Status':10s} {'Created (UTC)':20s} {'Reason':26s} Question")
    for r in rows:
        q = r["question"] if len(r["question"]) <= 60 else r["question"][:57] + "..."
        print(f"{_ref(r['id']):8s} {r['status']:10s} {r['created_at']:20s} {r['reason_code']:26s} {q}")


def cmd_show(ref):
    with closing(_connect()) as con:
        r = con.execute("SELECT * FROM escalations WHERE id = ?", (_row_number(ref),)).fetchone()
    if not r:
        print(f"{ref} was not found.")
        return
    for key in r.keys():
        print(f"{key:18s} {r[key]}")


def cmd_resolve(ref, resolution, category="Escalated"):
    """Closes an escalation and adds the human answer to the ticket history.

    The next run of ingest.py makes the new ticket searchable, so the bot can answer the
    same question itself. In a real system a person reviews the text before it goes live.
    """
    cfg = yaml.safe_load(Path("intent.yaml").read_text(encoding="utf-8"))
    t = cfg["sources"]["tickets"]
    with closing(_connect()) as con:
        r = con.execute("SELECT * FROM escalations WHERE id = ?", (_row_number(ref),)).fetchone()
        if not r:
            print(f"{ref} was not found.")
            return
        if r["status"] == "resolved":
            print(f"{ref} is already resolved as {r['ticket_id']}.")
            return
        with closing(sqlite3.connect(t["database"])) as tdb:
            last = tdb.execute(
                f"SELECT MAX(CAST(SUBSTR(ticket_id, 3) AS INTEGER)) FROM {t['table']}"
            ).fetchone()[0] or 1000
            ticket_id = f"T-{last + 1}"
            tdb.execute(
                f"INSERT INTO {t['table']} (ticket_id, model, category, question, resolution, status) VALUES (?,?,?,?,?,?)",
                (ticket_id, "Any", category, r["question"], resolution, "resolved"),
            )
            tdb.commit()
        con.execute(
            "UPDATE escalations SET status='resolved', resolution=?, resolved_at=?, ticket_id=? WHERE id=?",
            (resolution, _now(), ticket_id, r["id"]),
        )
        con.commit()
    print(f"{ref} resolved and saved as ticket {ticket_id}.")
    print("Next run python src/ingest.py, then restart the app, so the bot can use it.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["list"]:
        cmd_list()
    elif args[:1] == ["show"] and len(args) == 2:
        cmd_show(args[1])
    elif args[:1] == ["resolve"] and len(args) in (3, 4):
        cmd_resolve(*args[1:])
    else:
        print(__doc__)
