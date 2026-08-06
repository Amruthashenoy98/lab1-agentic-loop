"""
loop.py

Agentic loop that drives the classify_ticket tool until Claude has
confirmed all three classification fields: product_area, severity,
and intent. The loop keeps calling the tool as many times as Claude
requests, and only stops when Claude signals it is done (stop_reason
== "end_turn").
"""

import anthropic
from tools import classify_ticket

# Initialise client
client = anthropic.Anthropic()  

MODEL_NAME = "claude-sonnet-4-6"
MAX_TOKENS = 1024

#Test ticket
TEST_TICKET = """From: sarah.chen@globalcorp.com
Subject: Cannot access SSO login — entire team locked out

Our team of 40 has been unable to log in via SSO since 09:00 this morning.
We have a client demo in 3 hours. This is completely blocking us."""

#Tool registration
tools = [
    {
        "name": "classify_ticket",
        "description": (
            "Classify a support ticket and return values for the requested "
            "fields. Call this tool as many times as needed, requesting "
            "whichever fields are still missing, until product_area, "
            "severity, and intent have all been confirmed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_text": {
                    "type": "string",
                    "description": "The full raw text of the support ticket to classify.",
                },
                "fields_needed": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of field names to classify in this call. "
                        "Each must be one of: 'product_area', 'severity', 'intent'."
                    ),
                },
            },
            "required": ["ticket_text", "fields_needed"],
        },
    }
]

TOOL_FUNCTIONS = {
    "classify_ticket": classify_ticket,
}

#Build initial conversation
messages = [
    {
        "role": "user",
        "content": (
            "Classify the following support ticket completely. You must "
            "determine all three fields: product_area, severity, and intent. "
            "Use the classify_ticket tool as many times as needed — you may "
            "request one field at a time or several at once — until all "
            "three fields have been confirmed. Do not stop early, and do "
            "not call the tool again once all three fields are known.\n\n"
            f"Ticket:\n{TEST_TICKET}"
        ),
    }
]

#Agentic loop
iteration = 0
while True:
    iteration += 1

    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=MAX_TOKENS,
        tools=tools,
        messages=messages,
    )

    print(f"--- Iteration {iteration} | stop_reason: {response.stop_reason} ---")

    #append the assistans response
    messages.append({"role": "assistant", "content": response.content})

    if response.stop_reason == "end_turn":
        final_text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        print("\nFinal response:\n" + final_text)
        break

    elif response.stop_reason == "tool_use":
        tool_results = []

        for block in response.content:
            if block.type == "tool_use":
                func = TOOL_FUNCTIONS.get(block.name)
                if func is None:
                    raise ValueError(f"No implementation found for tool '{block.name}'")

                print(f"  Tool call: {block.name}({block.input})")
                result = func(**block.input)
                print(f"  Tool result: {result}")

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    }
                )

        
        messages.append({"role": "user", "content": tool_results})
        continue

    else:
        print(f"Unhandled stop_reason: {response.stop_reason}. Stopping loop.")
        break
