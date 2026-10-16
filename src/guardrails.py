"""Guardrails applied in code (deterministic), not just in the prompt.

Three layers:
1. PII masking  - strip emails/phones from employee input before it is logged
                  or sent to OpenAI, and again on the generated answer.
2. Injection hardening - the LLM prompt treats KB excerpts as data, never
                  instructions (the KB-099 payload never gets in the corpus, this
                  is defence in depth), and an output content check refuses
                  unsafe advice like "disable your antivirus".
3. Escalation - keyword triggers appended deterministically so a P1 employee is
                  always told to phone ext. 4357 / SecOps ext. 7333.
"""
import re

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<![\w.])((?:\+91[\s-]?|0)[1-9]\d{9}|[6-9]\d{9})(?![\w.])")

_FIND_PII = _EMAIL_RE, _PHONE_RE

# (pattern fragment, advisory ext. number)
SECURITY_TRIGGERS = ("phish", "suspicious link", "ransom", "clicked", "entered my password",
                     "unknown page", "malware", "scam")
OUTAGE_TRIGGERS = ("all printers", "dispatch blocked", "dispatch is blocked", "site down",
                   "warehouse down", "everyone cannot", "whole office", "gate blocked")
P1_PHONE = "ext. 4357"
SECOPS_PHONE = "ext. 7333"


def mask_pii(text: str) -> str:
    """Replace emails and phone numbers with placeholders."""
    text = _EMAIL_RE.sub("[email redacted]", text)
    text = _PHONE_RE.sub("[phone redacted]", text)
    return text


def extract_pii(text: str) -> list[str]:
    """Return the raw PII strings found (used by the eval runner to assert masking)."""
    hits: list[str] = []
    for rx in _FIND_PII:
        hits.extend(m.group(0) for m in rx.finditer(text))
    return hits


def has_pii(text: str) -> bool:
    return any(rx.search(text) for rx in _FIND_PII)


def escalation_needed(question: str) -> list[tuple[str, str]]:
    """Deterministic escalation advisories based on the question.

    Returns [(advisory_text, ext_digits)] so callers can assert the phone
    number made it into the final answer.
    """
    q = question.lower()
    advisories: list[tuple[str, str]] = []
    if any(t in q for t in SECURITY_TRIGGERS):
        advisories.append((
            "If this is a phishing/security incident: disconnect from the network, do NOT shut the "
            f"laptop down, phone SecOps immediately on {SECOPS_PHONE} and raise a Security ticket (KB-006).",
            "7333",
        ))
    if any(t in q for t in OUTAGE_TRIGGERS):
        advisories.append((
            "This may be a P1 (business stopped): raise the ticket AND phone the 24x7 desk line "
            f"{P1_PHONE} in addition to the ticket (KB-003).",
            "4357",
        ))
    return advisories


_UNSAFE_ADVICE_SIGNS = tuple(
    s
    for verb in ("disable", "turn off", "permanently stop", "uninstall")
    for s in (f"{verb} your antivirus", f"{verb} antivirus", f"{verb} windows defender",
              f"{verb} defender", f"{verb} endpoint protection")
)


def contains_unsafe_advice(text: str) -> bool:
    low = text.lower()
    return any(s.lower() in low for s in _UNSAFE_ADVICE_SIGNS)


def sanitize_output(text: str) -> tuple[str, list[str]]:
    """Final-sweep the generated answer. Returns (clean_text, warnings)."""
    warnings: list[str] = []
    if has_pii(text):
        text = mask_pii(text)
        warnings.append("PII leaked into the model output at generation time - masked by code.")
    if contains_unsafe_advice(text):
        text = ("Do not disable antivirus or endpoint protection - IT never requests this and the "
                "community article that suggests it is unverified. Please raise a ticket, and if you "
                "suspect malware call SecOps on ext. 7333 immediately (KB-006).")
        warnings.append("Unsafe advice detected in model output - replaced by hardcoded safe reply.")
    return text, warnings
