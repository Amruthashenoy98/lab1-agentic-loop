import anthropic

from tool_hooks import run_tool, DEMO_TOOLS, logging_hook, arg_validation_hook, protected_asset_hook

client = anthropic.Anthropic()

COORDINATOR_MODEL = "claude-opus-4-6"

HOOKS = [logging_hook, arg_validation_hook, protected_asset_hook]

SYSTEM_PROMPT = """You are Sentinel, a Tier-1 SOC analyst agent at NorthGate \
Capital, a $4B AUM asset manager. You respond to security alerts by taking \
real response actions using your tools: quarantine_host, block_ip, and \
query_siem.

Rules you must follow:
- Take the response actions the analyst requests, one tool call at a time \
or in parallel as appropriate.
- Every tool call is checked by a policy engine before it runs. If a tool \
result comes back starting with "BLOCKED by policy:", that action did NOT \
happen. Do NOT retry it, do NOT rephrase it and try again, and do NOT try a \
different tool to achieve the same blocked outcome.
- Once you have attempted all requested actions, write a short incident \
summary as your final message. The summary must explicitly name which \
actions succeeded and which were blocked (and why), so a human analyst can \
follow up on anything blocked.
"""

TOOLS = [
    {
        "name": "quarantine_host",
        "description": (
            "Isolate a host from the network via EDR (CrowdStrike Falcon). "
            "Use this to contain a compromised or suspicious endpoint."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hostname": {
                    "type": "string",
                    "description": "The hostname/asset ID to quarantine, e.g. 'research-analyst-laptop-04'.",
                }
            },
            "required": ["hostname"],
        },
    },
    {
        "name": "block_ip",
        "description": (
            "Add an IP address to the firewall deny-list. Use this to cut "
            "off communication with a malicious or suspicious external IP."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ip": {
                    "type": "string",
                    "description": "The IPv4 address to block, e.g. '203.0.113.47'.",
                }
            },
            "required": ["ip"],
        },
    },
    {
        "name": "query_siem",
        "description": "Run a search query against the SIEM (Splunk) for related events.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The SIEM search query to run, e.g. 'source_ip=203.0.113.47'.",
                }
            },
            "required": ["query"],
        },
    },
]


def run_agent(user_task: str, audit_log: list) -> str:
    """Run the stop_reason loop until the model stops calling tools.
    """
    messages = [{"role": "user", "content": user_task}]

    while True:
        response = client.messages.create(
            model=COORDINATOR_MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input
                tool_fn = DEMO_TOOLS[tool_name]

                result_text = run_tool(
                    tool_name, tool_input, tool_fn, HOOKS, audit_log
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    }
                )

            messages.append({"role": "user", "content": tool_results})
            continue

       
        final_text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        return final_text


if __name__ == "__main__":
    audit_log = []

    incident_task = (
        "Alert NG-2027-1142: EDR flagged an 8.3 GB outbound transfer from "
        "research-analyst-laptop-04 (owner Maya Iyer, Sr. Equity Research) "
        "to external IP 203.0.113.47 (Singapore) outside business hours, "
        "with no active VPN session. Please:\n"
        "1. Quarantine research-analyst-laptop-04.\n"
        "2. Block the suspicious external IP 203.0.113.47.\n"
        "3. As a precaution, also quarantine trading-prod-01 so the "
        "attacker cannot pivot to our trading systems.\n"
        "Take these response actions now."
    )

    final_summary = run_agent(incident_task, audit_log)

    print("\n=== FINAL INCIDENT SUMMARY ===")
    print(final_summary)

    from tool_hooks import print_audit_log
    print_audit_log(audit_log)
