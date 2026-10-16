"""Run the eval suite (evals/cases.yaml) and produce:

  - a rich green/red terminal table
  - docs/eval_report.md  (the reviewable scorecard)
  - docs/eval_results.json (raw outputs behind every verdict, for auditability)

Four checks per case, mirroring the brief's own scoring words:
  retrieval / answer / abstention / safety
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.answer import answer_with_details          # noqa: E402
from src import guardrails                          # noqa: E402
from src.config import (                            # noqa: E402
    ABSTAIN_SIM_THRESHOLD, CHAT_MODEL, EMBEDDING_MODEL,
)

console = Console()
EVALS_DIR = Path(__file__).resolve().parent
ROOT = EVALS_DIR.parent
REPORT_PATH = ROOT / "docs" / "eval_report.md"
RESULTS_JSON_PATH = ROOT / "docs" / "eval_results.json"

# Honest, curated note about known weaknesses (kept in code so it is versioned).
KNOWN_GAPS = f"""\
- The similarity-abstain threshold (`{ABSTAIN_SIM_THRESHOLD}`) was tuned on this
  tiny suite and no other questions; 400-ticket-a-day traffic needs a sweep on
  real tickets.
- No automatic re-ingestion trigger when an article's `status` changes -
  tomorrow's KB-002-style retirement would need a manual `python -m src.ingest`.
- Answer checks are keyword must/must-not rules, not a fact-level verifier; a
  checker that reads the cited paragraph and scores entailment would be stronger.
- `mask_pii` is regex-based; PII that does not look like an email/phone (IDs,
  addresses) is not caught. Presidio-style NER masking would be more robust.
- Single-turn only; multi-turn follow-up conversations are out of scope here.
"""


def report_header() -> str:
    return (
        "# Vectra KB assistant - eval report\n"
        f"\nGenerated: `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}`\n\n"
        f"Models: embeddings `{EMBEDDING_MODEL}`, chat `{CHAT_MODEL}` | "
        f"DB: Postgres 16 + pgvector (docker); 9 chunks ingested "
        f"(7 `current`, 2 excluded from retrieval: KB-002 `deprecated`, KB-099 `unverified`)\n\n"
        f"Abstain gate: cosine similarity < `{ABSTAIN_SIM_THRESHOLD}` -> abstain "
        "without calling the LLM.\n"
    )


def check_mark(ok: bool, na: bool = False) -> str:
    if na:
        return "n/a"
    return "PASS" if ok else "FAIL"


def build_report(results: list[dict], header: str) -> str:
    lines = [
        header,
        "## Case results\n",
        "| Case | Question (start) | Retrieval | Answer | Abstention | Safety | Overall |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['id']} | {r['question'][:46]} | "
            f"{check_mark(r['retrieval_ok'], r['retrieval_na'])} | "
            f"{check_mark(r['answer_ok'])} | "
            f"{check_mark(r['abstain_ok'], r['abstain_na'])} | "
            f"{check_mark(r['safety_ok'])} | "
            f"**{'PASS' if r['pass'] else 'FAIL'}** |"
        )
    lines.append("")

    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    lines.append("## Summary\n")
    lines.append(f"- **{passed}/{total} cases passed**")
    lines.append(
        f"- Safety axis: {sum(1 for r in results if r['safety_ok'])}/{total} "
        "(no PII echoed, no unsafe advice, phone escalation present where the KB demands it)"
    )

    fails = [r for r in results if not r["pass"]]
    if fails:
        lines.append("\n## Failing cases\n")
        for r in fails:
            lines.append(f"### {r['id']}")
            lines.append(f"Q: {r['question']}\n")
            lines.append("```json")
            lines.append(json.dumps(r["raw_output"], indent=2, ensure_ascii=False))
            lines.append("```\n")
            for issue in r["notes"]:
                lines.append(f"- {issue}")
    else:
        lines.append(
            "\nAll cases pass. Still worth reading the gap list below - a green\n"
            "scorecard on 12 hand-written cases is a starting point, not proof.\n"
        )

    lines.append("## What still fails / would improve before go-live\n")
    lines.append(KNOWN_GAPS)
    return "\n".join(lines) + "\n"


def run() -> list[dict]:
    cases = yaml.safe_load((EVALS_DIR / "cases.yaml").read_text(encoding="utf-8"))["cases"]
    results: list[dict] = []

    table = Table(title="Vectra KB assistant eval suite")
    for col in ("case", "retrieval", "answer", "abstention", "safety", "overall"):
        table.add_column(col)

    for case in cases:
        notes: list[str] = []
        ball = answer_with_details(case["question"])
        output_text = ball["answer"]

        # --- 1) retrieval: is one of the allowed doc(s) in the retrieved set? ---
        allowed = set(case.get("allowed_docs") or [])
        retrieved_ids = {d["doc_id"] for d in ball["retrieved"]}
        if allowed:
            retrieval_ok = bool(allowed & retrieved_ids)
            if not retrieval_ok:
                notes.append(f"allowed docs {sorted(allowed)} not retrieved; got {sorted(retrieved_ids)}")
            retrieval_na = False
        else:
            retrieval_na = True
            retrieval_ok = True

        # --- 2) answer content (must / should / must-not) ---
        answer_ok = True
        for s in case.get("must_contain", []):
            if s.lower() not in output_text.lower():
                answer_ok = False
                notes.append(f"answer must contain '{s}' but it did not")
        for s in case.get("should_contain", []):
            if s.lower() not in output_text.lower():
                notes.append(f"answer should contain '{s}' but it did not (advisory)")
        for s in case.get("must_not_contain", []):
            if s.lower() in output_text.lower():
                answer_ok = False
                notes.append(f"forbidden phrase '{s}' leaked into the answer")

        # --- 3) abstention ---
        abstain_na = "abstained" not in case
        abstain_ok = True
        if not abstain_na:
            want = bool(case["abstained"])
            got = bool(ball["abstained"])
            if want and allowed:
                notes.append("case config error: abstained=true with allowed_docs not empty")
                want = False
            if got != want:
                abstain_ok = False
                notes.append(
                    f"expected abstained={want}, assistant returned abstained={got} "
                    f"(best similarity {ball['best_similarity']:.2f}, gate {ABSTAIN_SIM_THRESHOLD})"
                )

        # --- 4) safety: PII never echoed; no unsafe advice; escalation exts present ---
        safety_ok = True
        if case.get("pii_in_question"):
            for pii in guardrails.extract_pii(case["question"]):
                if pii.lower() in output_text.lower():
                    safety_ok = False
                    notes.append(f"raw PII '{pii}' leaked into the answer")
            if guardrails.has_pii(output_text):
                safety_ok = False
                notes.append("answer still contains PII-shaped strings")
        if guardrails.contains_unsafe_advice(output_text):
            safety_ok = False
            notes.append("unsafe advice (disable antivirus/defender) leaked into the answer")
        for ext in case.get("must_phone", []):
            if ext.lower() not in output_text.lower():
                safety_ok = False
                notes.append(f"missing phone escalation ext. {ext} required by the KB")

        passed = retrieval_ok and answer_ok and abstain_ok and safety_ok
        row = (
            "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        )
        table.add_row(
            case["id"],
            check_mark(retrieval_ok, retrieval_na),
            check_mark(answer_ok),
            check_mark(abstain_ok, abstain_na),
            check_mark(safety_ok),
            row,
        )
        results.append(
            {
                "id": case["id"],
                "question": case["question"],
                "retrieval_ok": retrieval_ok,
                "retrieval_na": retrieval_na,
                "answer_ok": answer_ok,
                "abstain_ok": abstain_ok,
                "abstain_na": abstain_na,
                "safety_ok": safety_ok,
                "pass": passed,
                "notes": notes,
                "retrieved": ball["retrieved"],
                "raw_output": {
                    "answer": ball["answer"],
                    "citations": ball["citations"],
                    "abstained": ball["abstained"],
                    "warnings": ball["warnings"],
                },
            }
        )

    console.print(table)
    total = len(results)
    console.print(
        f"\n[green]{sum(1 for r in results if r['pass'])}/{total} passed.[/green] "
        "Report -> docs/eval_report.md | raw outputs -> docs/eval_results.json"
    )
    return results


def main() -> None:
    results = run()
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text(build_report(results, report_header()), encoding="utf-8")
    RESULTS_JSON_PATH.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    console.print(f"Report written to [bold]{REPORT_PATH.relative_to(ROOT)}[/bold]")


if __name__ == "__main__":
    main()
