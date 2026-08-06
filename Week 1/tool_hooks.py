"""
tool_hooks.py

Pure-Python PostToolUse hook engine for Sentinel (NorthGate Capital SOC
copilot)."""

import ipaddress
import fnmatch


# ---------------------------------------------------------------------------
# Protection lists

PROTECTED_HOSTS = [
    "trading-prod-*",       # all trading production servers
    "market-data-relay-*",  # market-data feed relays
    "ceo-laptop-*",         # executive laptops
    "cfo-laptop-*",
    "ciso-laptop-*",
]


PROTECTED_IPS = {
    "198.51.100.10",  # Reuters market-data
    "198.51.100.11",  # Bloomberg terminal
    "192.0.2.55",      # prime-broker API
    "192.0.2.56",      # clearing-house webhook
}


PROTECTED_EXEC_USERNAMES = {"ceo", "cfo", "ciso"}
PROTECTED_EXEC_DOMAIN_SUFFIX = "@northgate-exec"



# Hook functions -- signature: hook(tool_name, tool_input) -> (bool, str)
# ---------------------------------------------------------------------------

def logging_hook(tool_name, tool_input):
    print(f"[LOG] tool={tool_name} keys={list(tool_input.keys())}")
    return True, ""


def arg_validation_hook(tool_name, tool_input):
    if tool_name == "block_ip":
        ip = tool_input.get("ip")
        if not ip:
            return False, "block_ip requires an 'ip' argument, none was provided."
        try:
            ipaddress.IPv4Address(ip)
        except ValueError:
            return False, f"block_ip received an invalid IPv4 address: '{ip}'."
        return True, ""

    if tool_name == "quarantine_host":
        hostname = tool_input.get("hostname")
        if not hostname:
            return False, "quarantine_host requires a 'hostname' argument, none was provided."
        return True, ""

    if tool_name == "disable_user":
        username = tool_input.get("username")
        if not username:
            return False, "disable_user requires a 'username' argument, none was provided."
        return True, ""

    # No validation rules defined for this tool (e.g. query_siem) -- allow.
    return True, ""


def protected_asset_hook(tool_name, tool_input):
    if tool_name == "quarantine_host":
        hostname = tool_input.get("hostname", "")
        for pattern in PROTECTED_HOSTS:
            if fnmatch.fnmatch(hostname, pattern):
                return False, (
                    f"POLICY: '{hostname}' matches protected host pattern "
                    f"'{pattern}'. Quarantining protected production assets "
                    "is never permitted via this tool."
                )
        return True, ""

    if tool_name == "block_ip":
        ip = tool_input.get("ip", "")
        if ip in PROTECTED_IPS:
            return False, (
                f"POLICY: '{ip}' is a protected market-data / counterparty "
                "IP. Adding it to the firewall deny-list is never permitted."
            )
        return True, ""

    if tool_name == "disable_user":
        username = tool_input.get("username", "")
        lowered = username.lower()
        if lowered in PROTECTED_EXEC_USERNAMES or lowered.endswith(
            PROTECTED_EXEC_DOMAIN_SUFFIX
        ):
            return False, (
                f"POLICY: '{username}' is an executive account. Disabling "
                "executive accounts requires dual approval and cannot be "
                "done via this tool alone."
            )
        return True, ""

    return True, ""


# ---------------------------------------------------------------------------
# run_tool -- the gate that every tool call must pass through
# ---------------------------------------------------------------------------

def run_tool(tool_name, tool_input, tool_fn, hooks, audit_log):
    for hook in hooks:
        allowed, reason = hook(tool_name, tool_input)
        if not allowed:
            audit_log.append(
                {
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                    "status": "BLOCKED",
                    "reason": reason,
                }
            )
            print(f"[BLOCKED] tool={tool_name} input={tool_input} reason={reason}")
            return f"BLOCKED by policy: {reason}"

    result = tool_fn(tool_input)
    audit_log.append(
        {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "status": "allowed",
            "reason": "all hooks passed",
        }
    )
    return result


def print_audit_log(audit_log):
    print("\n=== AUDIT LOG ===")
    for i, entry in enumerate(audit_log, start=1):
        print(
            f"{i}. [{entry['status']}] {entry['tool_name']}"
            f"({entry['tool_input']}) -- {entry['reason'] or 'ok'}"
        )



# Demo tool simulators


def _sim_block_ip(tool_input):
    return f"[Firewall] IP {tool_input.get('ip')} added to deny-list (simulated)."


def _sim_quarantine_host(tool_input):
    return f"[EDR] Host {tool_input.get('hostname')} isolated from network (simulated)."


def _sim_disable_user(tool_input):
    return f"[IAM] User {tool_input.get('username')} account disabled (simulated)."


def _sim_query_siem(tool_input):
    return f"[SIEM] Query '{tool_input.get('query')}' executed, 0 new matches (simulated)."


DEMO_TOOLS = {
    "block_ip": _sim_block_ip,
    "quarantine_host": _sim_quarantine_host,
    "disable_user": _sim_disable_user,
    "query_siem": _sim_query_siem,
}




if __name__ == "__main__":
    hooks = [logging_hook, arg_validation_hook, protected_asset_hook]
    audit_log = []

    attempts = [
        # 1. ALLOWED: quarantine the suspicious analyst laptop (not protected).
        ("quarantine_host", {"hostname": "research-analyst-laptop-04"}),

        # 2. POLICY-BLOCK: quarantining a trading production server.
        ("quarantine_host", {"hostname": "trading-prod-01"}),

        # 3. ARG-VALIDATION BLOCK: malformed IP address.
        ("block_ip", {"ip": "999.999.999.999"}),

        # 4. ARG-VALIDATION BLOCK: empty username.
        ("disable_user", {"username": ""}),

        # 5. EXEC-ACCOUNT BLOCK: disabling the CEO's account.
        ("disable_user", {"username": "ceo"}),

        # A couple of extra allowed calls, to show the happy path too.
        ("block_ip", {"ip": "203.0.113.47"}),
        ("query_siem", {"query": "source_ip=203.0.113.47"}),
    ]

    for tool_name, tool_input in attempts:
        result = run_tool(
            tool_name, tool_input, DEMO_TOOLS[tool_name], hooks, audit_log
        )
        print(f"    -> result: {result}\n")

    print_audit_log(audit_log)
