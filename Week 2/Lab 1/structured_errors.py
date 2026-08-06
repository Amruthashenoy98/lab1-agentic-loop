import os
import re
import sys
import json
import time

import anthropic


_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _get_model() -> str:
    return os.environ["ANTHROPIC_MODEL"]


RETRYABLE = {408, 429, 500, 502, 503, 504}

ORDER_ID_PATTERN = re.compile(r"^NP-[0-9]{6}$")


# ---------------------------------------------------------------------------
# Mock Orders service + failure-injection helper
# ---------------------------------------------------------------------------

class ServiceError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"[{status}] {message}")


# A small database of real orders
ORDERS_DB = {
    "NP-100245": {
        "order_id": "NP-100245",
        "status": "in_transit",
        "items": ["4-Person Dome Tent"],
        "tracking": "1Z999AA10123456784",
    },
    "NP-100190": {
        "order_id": "NP-100190",
        "status": "delivered",
        "items": ["Waterproof Hiking Boots (Men's 10)"],
        "tracking": "1Z999AA10123456785",
    },
}


_FAILURE_QUEUE: dict = {}


def inject_failures(order_id: str, statuses: list) -> None:
    """Queue up transient failures for order_id. The next len(statuses)
    calls to orders_service(order_id) will raise ServiceError with each
    status in turn; calls after that behave normally."""
    _FAILURE_QUEUE[order_id] = list(statuses)


def orders_service(order_id: str) -> dict:
    """The raw (mock) backend call. Raises ServiceError on any failure;
    returns order fields as a plain dict on success."""

    # Permanent failure: malformed id, rejected before it would even reach
    # a real backend.
    if not ORDER_ID_PATTERN.match(order_id):
        raise ServiceError(
            400, f"Malformed order id '{order_id}'. Expected format NP-XXXXXX."
        )

    # Transient failure injection, if any are queued for this id.
    queue = _FAILURE_QUEUE.get(order_id)
    if queue:
        status = queue.pop(0)
        raise ServiceError(status, f"Simulated {status} error for {order_id}.")

    # Permanent failure: no such order.
    order = ORDERS_DB.get(order_id)
    if order is None:
        raise ServiceError(404, f"No order found with id '{order_id}'.")

    return order




def call_order_tool(order_id: str) -> dict:
    """Wrap orders_service and convert any ServiceError into a structured
    dict. This function must NEVER raise."""
    try:
        data = orders_service(order_id)
        return {"isError": False, **data}
    except ServiceError as err:
        return {
            "isError": True,
            "isRetryable": err.status in RETRYABLE,
            "status": err.status,
            "error": err.message,
        }


def run_with_retry(order_id: str, max_attempts: int = 4) -> dict:
    """Retry while isRetryable, with exponential backoff and a cap. Stop
    immediately on a permanent error."""
    delay = 0.2
    for attempt in range(1, max_attempts + 1):
        result = call_order_tool(order_id)
        if not result["isError"]:
            return result
        if result["isRetryable"] and attempt < max_attempts:
            time.sleep(delay)
            delay *= 2  # exponential backoff
            continue
        return result  # permanent, or out of attempts -> stop




def run_offline_self_check() -> None:
    print("=== OFFLINE SELF-CHECK (no API calls) ===\n")

    # 1. A good id succeeds.
    result = call_order_tool("NP-100245")
    print("1. Good id (NP-100245):", result)
    assert result["isError"] is False
    assert result["order_id"] == "NP-100245"
    print("   PASS: succeeded with order fields.\n")

    # 2. A 404 is a non-retryable error.
    result = call_order_tool("NP-999999")
    print("2. Unknown id (NP-999999):", result)
    assert result["isError"] is True
    assert result["status"] == 404
    assert result["isRetryable"] is False
    print("   PASS: 404 is non-retryable.\n")

    # 3. A queued 503 is a retryable error, and run_with_retry recovers
    #    once the service starts behaving.
    inject_failures("NP-100190", [503])
    single_call_result = call_order_tool("NP-100190")
    print("3a. Single call while 503 is queued:", single_call_result)
    assert single_call_result["isError"] is True
    assert single_call_result["status"] == 503
    assert single_call_result["isRetryable"] is True
    print("    PASS: 503 is retryable.\n")

    # Re-queue the same one-time 503 and prove run_with_retry recovers.
    inject_failures("NP-100190", [503])
    retried_result = run_with_retry("NP-100190", max_attempts=4)
    print("3b. run_with_retry over the same queued 503:", retried_result)
    assert retried_result["isError"] is False
    assert retried_result["order_id"] == "NP-100190"
    print("    PASS: run_with_retry retried past the transient 503 and succeeded.\n")

    print("All offline checks passed.")



#  live agent over three failure shapes


TOOLS = [
    {
        "name": "get_order_status",
        "description": (
            "Retrieve the status of an existing NorthPeak order by its order "
            "ID (shipping status, items, tracking). Use this whenever the "
            "customer gives an order number. The result may indicate an "
            "error -- read isError, isRetryable, status, and error carefully "
            "before responding to the customer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Order ID in the format 'NP-XXXXXX'.",
                }
            },
            "required": ["order_id"],
        },
    }
]

SYSTEM_PROMPT = """You are a NorthPeak Outfitters customer-support agent. \
You look up existing orders using the get_order_status tool.

The tool never crashes -- it always returns a result. Read the result \
carefully:
- If "isError" is false, the order was found; answer the customer's \
question using the order fields.
- If "isError" is true and "status" is 404, the order was not found. Tell \
the customer their order id doesn't match anything on file and ask them to \
double check it.
- If "isError" is true and "status" is 400, the order id was malformed. \
Ask the customer for a correctly formatted order id (the format is \
NP-XXXXXX, e.g. NP-100245).
- Any retrying of transient failures has ALREADY happened before you see \
the result. Do not call the tool again for the same order id after seeing \
an error -- just report the outcome to the customer.
"""


def run_agent_turn(user_message: str) -> str:
    messages = [{"role": "user", "content": user_message}]

    client = _get_client()
    model = _get_model()

    while True:
        response = client.messages.create(
            model=model,
            max_tokens=600,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Invariant: append the assistant turn to messages FIRST, before
        # branching on stop_reason.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                order_id = block.input.get("order_id", "")
                result = run_with_retry(order_id)

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                        "is_error": result["isError"],
                    }
                )

            messages.append({"role": "user", "content": tool_results})
            continue

        final_text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        return final_text


def run_live_demo() -> None:
    print("=== LIVE AGENT: THREE FAILURE SHAPES ===\n")

    # Case A: NP-100245 times out once (504), then succeeds on retry.
    inject_failures("NP-100245", [504])
    print("--- Case A: NP-100245, one 504 then success ---")
    answer_a = run_agent_turn(
        "Where is my order NP-100245? I think it might be delayed."
    )
    print("Agent:", answer_a, "\n")

    # Case B: NP-999999 doesn't exist -- 404, no retry.
    print("--- Case B: NP-999999, not found ---")
    answer_b = run_agent_turn("Can you check on order NP-999999?")
    print("Agent:", answer_b, "\n")

    # Case C: malformed id (missing the NP- prefix) -- 400, no retry.
    print("--- Case C: malformed id '100245' ---")
    answer_c = run_agent_turn("What's the status of order 100245?")
    print("Agent:", answer_c, "\n")


if __name__ == "__main__":
    if "--check" in sys.argv:
        run_offline_self_check()
    else:
        run_live_demo()