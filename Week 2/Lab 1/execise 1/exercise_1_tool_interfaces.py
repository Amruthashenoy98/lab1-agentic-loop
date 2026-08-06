"""
Proves that tool-selection reliability is an INTERFACE problem, not a
model-size problem, by running the SAME model over the SAME six questions
twice -- once with a weak toolset, once with a strong one -- and comparing
how often each set routes to the correct tool.

"""

import anthropic

client = anthropic.Anthropic()


MODEL = os.environ["ANTHROPIC_MODEL"]




WEAK_TOOLS = [
    {
        "name": "search",
        "description": "Search for stuff in the system.",
        "input_schema": {
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        },
    },
    {
        "name": "lookup",
        "description": "Look up information in the system.",
        "input_schema": {
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        },
    },
]

# Which weak tool plays which role, for scoring purposes.
WEAK_ROLE_MAP = {
    "catalog": "search",
    "order": "lookup",
}


# ---------------------------------------------------------------------------
# STRONG toolset: object+action names, descriptions that defer to the sibling
# tool, and typed/specific parameters (regex-constrained order_id).
# ---------------------------------------------------------------------------

STRONG_TOOLS = [
    {
        "name": "search_products",
        "description": (
            "Search the NorthPeak product CATALOG for items we sell (tents, "
            "sleeping bags, stoves, boots, etc.) by free-text query. Use this for "
            "availability, price, or whether a product exists. Do NOT use this to "
            "check something a customer already bought — for an existing purchase "
            "use get_order_status instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text product query, e.g. '4 person tent'."},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_order_status",
        "description": (
            "Retrieve the status of an EXISTING customer order by its order ID "
            "(shipping status, items, tracking). Use this whenever the customer "
            "gives an order number or references a purchase. Do NOT use this to "
            "browse the catalog — for products use search_products instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order ID in the format 'NP-XXXXXX'.", "pattern": "^NP-[0-9]{6}$"},
            },
            "required": ["order_id"],
        },
    },
]

STRONG_ROLE_MAP = {
    "catalog": "search_products",
    "order": "get_order_status",
}


# ---------------------------------------------------------------------------
# Six test cases: three catalog questions, three existing-order questions.
# ---------------------------------------------------------------------------

TEST_CASES = [
    {"question": "Do you carry a four-person tent?", "expected_role": "catalog"},
    {"question": "Where is my order NP-100245?", "expected_role": "order"},
    {"question": "Do you sell waterproof hiking boots?", "expected_role": "catalog"},
    {"question": "Can you check the status of NP-100190?", "expected_role": "order"},
    {"question": "I'm looking for a lightweight sleeping bag for winter camping.", "expected_role": "catalog"},
    {"question": "My order NP-100033 hasn't arrived yet, what's going on?", "expected_role": "order"},
]


# ---------------------------------------------------------------------------
# Scoring harness
# ---------------------------------------------------------------------------

def run_harness(tool_set: list, role_map: dict, label: str) -> int:
    """Run all six test cases against tool_set, forcing a tool call with
    tool_choice={'type': 'any'}. Print OK/MISS per question and return the
    total number correct."""

    # Reverse map: tool name -> role, so we can check what was picked.
    tool_name_to_role = {v: k for k, v in role_map.items()}

    print(f"\n=== {label} ===")
    correct = 0

    for case in TEST_CASES:
        question = case["question"]
        expected_role = case["expected_role"]
        expected_tool = role_map[expected_role]

        response = client.messages.create(
            model=MODEL,
            max_tokens=300,
            tools=tool_set,
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": question}],
        )

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            # Shouldn't happen with tool_choice="any", but guard anyway.
            picked_tool = None
        else:
            picked_tool = tool_use_blocks[0].name

        picked_role = tool_name_to_role.get(picked_tool, "UNKNOWN")
        is_correct = picked_tool == expected_tool

        status = "OK  " if is_correct else "MISS"
        print(
            f"[{status}] \"{question}\" "
            f"expected={expected_tool} ({expected_role})  "
            f"got={picked_tool} ({picked_role})"
        )

        if is_correct:
            correct += 1

    print(f"-- {label}: {correct}/{len(TEST_CASES)} correct --")
    return correct


if __name__ == "__main__":
    weak_score = run_harness(WEAK_TOOLS, WEAK_ROLE_MAP, "WEAK toolset")
    strong_score = run_harness(STRONG_TOOLS, STRONG_ROLE_MAP, "STRONG toolset")

    print("\n=== SUMMARY ===")
    print(f"Weak toolset:   {weak_score}/{len(TEST_CASES)}")
    print(f"Strong toolset: {strong_score}/{len(TEST_CASES)}")
    print("Same model, same questions -- only the tool interface changed.")
