"""Runs every question in tests/questions.csv through the agent and prints a scorecard.

Run from the project folder
  python src/evaluate.py

Rules
  answer    passes if the bot answers AND cites the expected source
  escalate  passes if the bot hands off to a human
  either    either result is fine, so it is marked REVIEW for you to read
  safe      passes if the reply leaks none of the must_not_contain text, whatever the decision
  Any question fails if the reply contains text from the must_not_contain column.
"""
import csv
import time
from pathlib import Path

from graph import ask, cfg

ROWS = list(csv.DictReader(open("tests/questions.csv", encoding="utf-8")))


def judge_row(row, out):
    decision = out["decision"]
    expected = row["expected_decision"].strip()
    wanted = row["expected_source"].strip()
    sources = {s["source"] for s in out.get("sources", [])}
    text = out.get("answer", "").lower()

    leaks = [w for w in row["must_not_contain"].split("|") if w and w.lower() in text]
    if leaks:
        return "FAIL", "reply contains " + ", ".join(leaks)
    if expected == "safe":
        return "PASS", "nothing leaked"
    if expected == "either":
        return "REVIEW", "read the reply"
    if expected == "answer":
        if decision != "answer":
            return "FAIL", f"handed off ({out.get('escalation_reason')})"
        if wanted and wanted not in sources:
            return "FAIL", f"cited {', '.join(sorted(sources)) or 'nothing'} instead of {wanted}"
        return "PASS", ""
    if decision != "escalate":
        return "FAIL", "answered a question it should hand off"
    return "PASS", ""


def main():
    results = []
    for row in ROWS:
        start = time.time()
        out = ask(row["question"], log=False)
        status, note = judge_row(row, out)
        results.append((row, out, status, note, time.time() - start))
        print(f"{row['id']:3s} {status:6s} {out['decision']:9s} sim={out['top_sim']:.3f}  {note}")

    print()
    header = f"{'ID':3s} {'Type':10s} {'Expected':9s} {'Got':9s} {'Sim':>6s} {'Judge':5s} {'Fact':6s} {'Secs':>5s}  Result"
    print(header)
    print("-" * len(header))
    for row, out, status, note, secs in results:
        v = out.get("verified")
        fact = "pass" if v is True else ("fail" if v is False else "-")
        print(
            f"{row['id']:3s} {row['category']:10s} {row['expected_decision']:9s} {out['decision']:9s} "
            f"{out['top_sim']:6.3f} {out.get('judge_verdict', '-'):5s} {fact:6s} {secs:5.1f}  {status}"
        )

    counts = {k: sum(1 for r in results if r[2] == k) for k in ("PASS", "FAIL", "REVIEW")}
    print(f"\nPASS {counts['PASS']}   FAIL {counts['FAIL']}   REVIEW {counts['REVIEW']}   of {len(results)}")

    should_answer = [r[1]["top_sim"] for r in results if r[0]["expected_decision"] == "answer"]
    stopped_early = [r for r in results if r[1].get("escalation_reason") == "out_of_scope"]
    should_escalate = [
        r[1]["top_sim"]
        for r in results
        if r[0]["expected_decision"] == "escalate" and r[1].get("escalation_reason") != "out_of_scope"
    ]
    R = cfg["retrieval"]
    print("\nThreshold check")
    if should_answer and should_escalate:
        low, high = min(should_answer), max(should_escalate)
        print(f"  Lowest score among questions that should be answered   {low:.3f}")
        print(f"  Highest score among questions that should be handed off {high:.3f}")
        if low > high:
            print("  The two groups do not overlap, so a clean line exists between them.")
        else:
            print("  The groups overlap. Similarity alone cannot separate them, which is why the judge exists.")
    if stopped_early:
        print(f"  {len(stopped_early)} question(s) were stopped by the scope check before retrieval, so they are left out of this comparison.")
    print(f"  Current settings  min_similarity {R['min_similarity']}   borderline_floor {R['borderline_floor']}")

    print("\nReplies to read")
    for row, out, status, note, secs in results:
        if status in ("REVIEW", "FAIL"):
            print(f"\n[{row['id']}] {status}  {row['question']}")
            print(f"  decision {out['decision']}   reason {out.get('escalation_reason') or '-'}   sources {[s['id'] for s in out.get('sources', [])]}")
            print("  " + out.get("answer", "").replace("\n", "\n  "))
            if out.get("escalation_reason") == "unsupported_claims":
                print("  REJECTED DRAFT")
                print("  " + out.get("draft", "").replace("\n", "\n  "))
                print("  FACT CHECK SAID")
                print("  " + out.get("verify_note", "").replace("\n", "\n  "))

    path = Path("tests/results.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "category", "question", "expected", "decision", "top_sim", "judge", "verified", "reason", "sources", "result", "answer"])
        for row, out, status, note, secs in results:
            w.writerow([
                row["id"], row["category"], row["question"], row["expected_decision"], out["decision"],
                round(out["top_sim"], 3), out.get("judge_verdict", ""), out.get("verified", ""),
                out.get("escalation_reason", ""), "|".join(s["id"] for s in out.get("sources", [])),
                status, out.get("answer", ""),
            ])
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
