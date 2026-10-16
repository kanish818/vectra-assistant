import json
import sys
from src.answer import answer_with_details

tests = [
    "My account got locked. How long until it unlocks by itself?",
    "What VPN server address should I use when working from home?",
    "What is the resolution target for a P2 ticket?",
    "How do I get a parking pass for the Gurugram office?",
    "Hi, I'm Anand Sharma (anand.sharma@vectralogistics.example, +91 9876543210). "
    "Company mail doesn't show up in my iPhone's built-in Mail app. How do I fix it?",
]

for i, q in enumerate(tests, 1):
    r = answer_with_details(q)
    print(f"--- Q{i} ---")
    print("Q:", q[:80])
    print("RET:", [(d["doc_id"], round(d["similarity"], 3)) for d in r["retrieved"][:2]])
    print("CITES:", r["citations"], "| ABSTAINED:", r["abstained"])
    print("ANSWER:", r["answer"].replace("\n", " ")[:300])
    if r["warnings"]:
        print("WARN:", "; ".join(r["warnings"]))
    sys.stdout.flush()
