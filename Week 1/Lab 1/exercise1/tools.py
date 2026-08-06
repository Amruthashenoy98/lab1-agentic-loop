"""
tools.py

Defines the classify_ticket tool used by the agentic loop in loop.py.

"""

import random

# Field vocabulary
PRODUCT_AREAS = ["Billing", "Platform", "Integrations", "Security", "Onboarding"]
SEVERITIES = ["P1-Critical", "P2-High", "P3-Medium", "P4-Low"]
INTENTS = ["Bug", "Question", "Feature Request", "Billing Dispute"]

FIELD_VOCAB = {
    "product_area": PRODUCT_AREAS,
    "severity": SEVERITIES,
    "intent": INTENTS,
}


def classify_ticket(ticket_text: str, fields_needed: list) -> dict:
    """
    Simulate classification of a support ticket.

    Args:
        ticket_text: The raw text of the support ticket.
        fields_needed: List of field names to classify. Each must be one
            of: "product_area", "severity", "intent".

    Returns:
        A dictionary containing only the requested fields, each mapped
        to a simulated value drawn from that field's vocabulary.
    """
    result = {}
    for field in fields_needed:
        if field not in FIELD_VOCAB:
            raise ValueError(
                f"Unknown field '{field}'. Must be one of {list(FIELD_VOCAB.keys())}"
            )
        result[field] = random.choice(FIELD_VOCAB[field])
    return result
