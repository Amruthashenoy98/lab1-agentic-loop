"""
subagents.py

Four single-responsibility subagents used by the coordinator in a support-ticket
triage pipeline: Classifier, CRM Enricher, Drafter, and Validator.

"""

import json
import re

import anthropic

client = anthropic.Anthropic()

SUBAGENT_MODEL = "claude-haiku-4-5-20251001"


def _strip_code_fences(text: str) -> str:
    """Remove ``` or ```json markdown code fences that models sometimes wrap
    JSON responses in, so the remaining text is safe to pass to json.loads()."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def run_classifier(ticket: str) -> dict:
    system_prompt = (
        "You are a support-ticket classifier. Read the ticket and classify it "
        "into exactly three fields: product_area, severity, and intent. "
        "Respond ONLY in valid JSON with keys product_area, severity, and "
        "intent — no prose, no markdown, no code fences."
    )

    response = client.messages.create(
        model=SUBAGENT_MODEL,
        max_tokens=300,
        system=system_prompt,
        messages=[{"role": "user", "content": ticket}],
    )

    raw_text = response.content[0].text
    cleaned = _strip_code_fences(raw_text)
    return json.loads(cleaned)


def run_crm_enricher(customer_email: str, classification: dict) -> dict:
    system_prompt = (
        "You simulate a CRM lookup for a support ticket. Given a customer "
        "email and the ticket's classification, return a plausible customer "
        "account record. Respond ONLY in valid JSON with keys: account_tier, "
        "sla_tier, account_manager, and contract_value — no prose, no "
        "markdown, no code fences."
    )

    user_content = (
        f"Customer email: {customer_email}\n"
        f"Ticket classification: {json.dumps(classification)}\n\n"
        "Return a simulated CRM record for this customer as JSON with keys "
        "account_tier, sla_tier, account_manager, and contract_value."
    )

    response = client.messages.create(
        model=SUBAGENT_MODEL,
        max_tokens=300,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = response.content[0].text
    cleaned = _strip_code_fences(raw_text)
    return json.loads(cleaned)


def run_drafter(ticket: str, classification: dict, crm: dict) -> str:
    system_prompt = (
        "You are a customer support drafter. Write a professional, empathetic "
        "first-response email to the customer. Reference the customer's SLA "
        "tier so they know what response time to expect. Do not invent facts "
        "beyond what is provided."
    )

    context = (
        f"Original ticket:\n{ticket}\n\n"
        f"Classification:\n{json.dumps(classification)}\n\n"
        f"CRM record:\n{json.dumps(crm)}\n\n"
        "Using the information above, draft a first-response email to the "
        "customer. Reference their SLA tier explicitly."
    )

    response = client.messages.create(
        model=SUBAGENT_MODEL,
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": context}],
    )

    return response.content[0].text


def run_validator(draft: str, classification: dict, crm: dict) -> str:
    system_prompt = (
        "You are a quality-control validator for customer support emails. "
        "Check the draft against the provided classification and CRM record "
        "for: (1) correct product area, (2) a response-time commitment that "
        "matches the customer's SLA tier and account tier, and (3) "
        "professional tone. Reply with exactly the word APPROVED if the "
        "draft passes all checks, or otherwise reply with a bulleted list of "
        "the specific issues found."
    )

    user_content = (
        f"Draft email:\n{draft}\n\n"
        f"Classification (expected product area):\n{json.dumps(classification)}\n\n"
        f"CRM record (SLA tier: {crm.get('sla_tier')}, "
        f"account tier: {crm.get('account_tier')}):\n{json.dumps(crm)}\n\n"
        "Validate the draft against this classification and CRM record."
    )

    response = client.messages.create(
        model=SUBAGENT_MODEL,
        max_tokens=400,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    return response.content[0].text