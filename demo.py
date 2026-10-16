"""Interactive demo loop for the recruiter walkthrough.

  python demo.py              - type questions, Ctrl+C / 'quit' to exit
  python demo.py --samples    - one pass over the 5 official sample questions
"""
from __future__ import annotations

import json
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.answer import answer_with_details
from src.config import TOP_K
from src.guardrails import mask_pii

console = Console()

SAMPLE_QUESTIONS = [
    "My account got locked. How long until it unlocks by itself?",
    "What VPN server address should I use when working from home?",
    "What is the resolution target for a P2 ticket?",
    "How do I get a parking pass for the Gurugram office?",
    "Hi, I'm Anand Sharma (anand.sharma@vectralogistics.example, +91 9876543210). "
    "Company mail doesn't show up in my iPhone's built-in Mail app. How do I fix it?",
]


def show(question: str) -> None:
    r = answer_with_details(question)
    masked = mask_pii(question)
    console.rule(f"[bold blue]Q:[/] {question}")

    if masked != question:
        console.print(
            Panel(
                f"Sent to OpenAI: {masked}",
                title="guardrail [PII masked out before any LLM call]",
                border_style="magenta",
            )
        )

    # Retrieval trace
    bars = Table(show_header=False, box=None, padding=(0, 1))
    bars.add_column(justify="left")  # doc id
    bars.add_column()                # similarity bar
    bars.add_column()                # sim value
    for d in r["retrieved"][:TOP_K]:
        sim = d["similarity"]
        color = "green" if sim >= 0.30 else "yellow"
        bar = Text(f"{'█' * round(max(sim, 0.0) * 30):<{30}}", style=color)
        bars.add_row(Text(f" {d['doc_id']}", style="bold"), bar, Text(f"{sim:.2f}", style=color))
    console.print(
        Panel(
            bars,
            title="pgvector retrieval (cosine, status = 'current' filter)",
            border_style="cyan",
        )
    )

    # Result
    abstain = r["abstained"]
    style = "red" if abstain else "green"
    header = (
        "ABSTAINED - KB does not cover this (suggest raising a ticket)"
        if abstain
        else f"citations: {r['citations']}"
    )
    console.print(
        Panel(r["answer"], title=f"answer()  |  {header}", border_style=style)
    )
    if r["warnings"]:
        console.print(
            Panel(
                "\n".join(f"- {w}" for w in r["warnings"]),
                title="guardrail warnings (code-enforced)",
                border_style="yellow",
            )
        )
    console.print()


def main() -> None:
    # Windows consoles default to cp1252; block chars need UTF-8 out.
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
    console.print(
        Panel(
            "Vectra Logistics IT service desk assistant\n"
            "answer(question) -> { answer, citations, abstained }",
            title="by K. - take-home demo",
            border_style="blue",
        )
    )
    if "--samples" in sys.argv:
        for q in SAMPLE_QUESTIONS:
            show(q)
        return
    console.print("Ask anything (or 'quit'). Tip: paste an email/phone and watch the masker.\n")
    while True:
        try:
            q = console.input("[bold]you> [/bold]").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in {"quit", "exit", "q"}:
            break
        show(q)


if __name__ == "__main__":
    main()
