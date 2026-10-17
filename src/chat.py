from graph import ask

print("Customer Support Agent. Type a question, or press Enter on an empty line to quit.\n")

while True:
    q = input("You > ").strip()
    if not q:
        break
    out = ask(q)
    print(f"\n[{out['decision'].upper()}]  top_sim={out['top_sim']:.3f}  judge_used={out['judge_used']}"
          f"  judge={out.get('judge_verdict', '-')}  reason={out.get('escalation_reason') or '-'}")
    print(out["answer"])
    for s in out.get("sources", []):
        print(f"   source {s['id']}  ({s['title']})")
    if out["decision"] == "escalate":
        print("   handoff", out["handoff"])
    print()