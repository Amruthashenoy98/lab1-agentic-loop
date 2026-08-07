"""
exercise_3_tool_choice.py

tool_choice scopes what the model may do on a single turn. This script runs
the SAME four support tickets under three different tool_choice settings and
observes which one reliably produces a classification every time:

"""

import os

import anthropic

client = anthropic.Anthropic()

MODEL = os.environ["ANTHROPIC_MODEL"]


CLASSIFY_TOOL = {
    "name": "classify_ticket",
    "description": "Classify a support ticket into exactly one routing category.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["order_issue", "product_question", "return_request", "other"],
            },
            "reason": {"type": "string"},
        },
        "required": ["category", "reason"],
    },
}

DRAFT_TOOL = {
    "name": "draft_customer_reply",
    "description": "Draft a friendly reply message to send directly to the customer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reply_text": {"type": "string"},
        },
        "required": ["reply_text"],
    },
}

TOOLS = [CLASSIFY_TOOL, DRAFT_TOOL]



#three tool_choice modes


modes = {
    "auto": {"type": "auto"},
    "any": {"type": "any"},
    "FORCED": {"type": "tool", "name": "classify_ticket"},
}



TICKETS = [
    "My order NP-100245 never arrived and it's been 2 weeks. Where is it?",
    "Does the 4-person tent come in a green color option?",
    "I want to return the sleeping bag I bought last month, it's too small for me.",
    "Hey, just wanted to say your website is really easy to use, nice work!",
]


def run_ticket(ticket: str, tool_choice: dict):
    """Send one ticket through the API under a given tool_choice setting.
    Returns the raw response.content blocks for inspection."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        tools=TOOLS,
        tool_choice=tool_choice,
        messages=[{"role": "user", "content": ticket}],
    )
    return response.content


def describe_blocks(blocks) -> str:
    parts = []
    for block in blocks:
        if block.type == "text":
            snippet = block.text.strip().replace("\n", " ")
            if len(snippet) > 70:
                snippet = snippet[:70] + "..."
            parts.append(f'TEXT: "{snippet}"')
        elif block.type == "tool_use":
            parts.append(f"TOOL_USE: {block.name}({block.input})")
    return " | ".join(parts) if parts else "(empty response)"


def got_classification(blocks) -> bool:
    """True only if a classify_ticket tool_use block is present."""
    return any(
        block.type == "tool_use" and block.name == "classify_ticket"
        for block in blocks
    )


def run_mode(mode_name: str, tool_choice: dict) -> int:
    print(f"\n=== MODE: {mode_name}  (tool_choice={tool_choice}) ===")
    classified_count = 0

    for ticket in TICKETS:
        blocks = run_ticket(ticket, tool_choice)
        classified = got_classification(blocks)
        classified_count += int(classified)

        status = "CLASSIFIED" if classified else "NOT CLASSIFIED"
        print(f'[{status}] "{ticket[:60]}..."')
        print(f"    -> {describe_blocks(blocks)}")

    print(f"-- {mode_name}: {classified_count}/{len(TICKETS)} tickets classified --")
    return classified_count


if __name__ == "__main__":
    results = {}
    for mode_name, tool_choice in modes.items():
        results[mode_name] = run_mode(mode_name, tool_choice)

    print("\n=== SUMMARY ===")
    for mode_name, count in results.items():
        print(f"{mode_name:8s}: {count}/{len(TICKETS)} tickets reliably classified")

    print(
        "\nRule of thumb: use the NARROWEST tool_choice that still lets the "
        "step do its job. A deterministic routing step -- like triage -- "
        "needs 'FORCED' (tool_choice={'type': 'tool', 'name': "
        "'classify_ticket'}), not 'auto' or even 'any'."
    )