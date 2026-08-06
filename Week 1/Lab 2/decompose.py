import json

import anthropic

client = anthropic.Anthropic()

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def ask_claude(system: str, user: str, max_tokens: int, model: str = DEFAULT_MODEL) -> str:
    """One-shot wrapper around client.messages.create(). Every function in
    this module -- fixed or adaptive -- goes through this single helper."""
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text.strip()




def run_fixed_intel_digest(overnight_feed: str, asset_inventory: str) -> dict:
    """Three hardcoded steps, run in order, every time: extract IoCs, enrich
    against NorthGate's asset inventory, then write an exec brief."""

    # extract IoCs.
    ioc_system = (
        "Extract every indicator of compromise as a JSON list of "
        "{type, value, context} objects where type is one of "
        "ip/hash/domain/cve. Return ONLY the JSON array."
    )
    iocs_raw = ask_claude(ioc_system, overnight_feed, max_tokens=800)
    iocs_cleaned = iocs_raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        iocs = json.loads(iocs_cleaned)
    except json.JSONDecodeError:
        iocs = []  # defensive: don't crash the digest on a malformed extraction

    # enrich against what NorthGate actually owns/uses.
    enrich_system = (
        "You are a SOC threat-intel analyst. You will be given a list of "
        "indicators of compromise (IoCs) and NorthGate Capital's asset "
        "inventory. List every IoC that matches something NorthGate owns or "
        "uses. Give one bullet per match, naming the specific IoC and the "
        "specific asset it matches. If nothing matches, say so plainly."
    )
    enrich_user = (
        f"IoCs:\n{json.dumps(iocs, indent=2)}\n\n"
        f"NorthGate asset inventory:\n{asset_inventory}"
    )
    matches = ask_claude(enrich_system, enrich_user, max_tokens=600)

    # exec brief for the 08:00 standup.
    brief_system = (
        "You are writing a three-bullet executive brief for the SOC "
        "manager's 08:00 standup. Each bullet must name the asset and the "
        "recommended next action. Be concise -- executives read this in "
        "under thirty seconds."
    )
    brief_user = (
        f"IoCs:\n{json.dumps(iocs, indent=2)}\n\n"
        f"Matches against NorthGate assets:\n{matches}"
    )
    exec_brief = ask_claude(brief_system, brief_user, max_tokens=400)

    return {"iocs": iocs, "matches": matches, "exec_brief": exec_brief}




TRIAGE_BRANCHES = {
    "phishing": (
        "You are a SOC phishing-response analyst. Playbook: identify the "
        "delivery vector and any users who interacted with the message, "
        "contain by disabling malicious links/attachments and resetting "
        "credentials for any user who entered them, collect the email "
        "headers and payload as evidence, and escalate to the incident "
        "response lead if more than one user clicked through or if "
        "credentials were entered."
    ),
    "malware": (
        "You are a SOC malware-response analyst. Playbook: identify the "
        "malware family and affected host(s), contain by isolating the "
        "host from the network, collect the binary/hash and process tree "
        "as evidence, and escalate to incident response if the malware has "
        "persistence mechanisms or is spreading laterally."
    ),
    "lateral_movement": (
        "You are a SOC lateral-movement analyst investigating an attacker "
        "moving between hosts inside the network. Playbook: map every host "
        "and account touched so far, contain by isolating affected hosts "
        "and rotating credentials for touched accounts, collect "
        "authentication and network logs as evidence, and escalate "
        "immediately to incident response given the scope of compromise."
    ),
    "data_exfiltration": (
        "You are a SOC data-exfiltration analyst. Playbook: identify the "
        "data moved, destination, and volume, contain by blocking the "
        "destination IP/domain and isolating the source host, collect "
        "network flow logs and DLP alerts as evidence, and escalate to "
        "incident response and legal/compliance if regulated or "
        "client data was involved."
    ),
    "brute_force": (
        "You are a SOC brute-force / credential-attack analyst. Playbook: "
        "identify the targeted account(s) and source IP(s), contain by "
        "blocking the source IP and forcing a password reset on targeted "
        "accounts, collect authentication logs as evidence, and escalate "
        "to incident response if any login attempt succeeded."
    ),
    "false_positive": (
        "You are a SOC triage analyst closing out a benign alert. Playbook: "
        "briefly state why the activity is expected/benign, note any "
        "detection-rule tuning that would reduce future noise, and close "
        "out the alert with no further action required."
    ),
}


def classify_alert(alert_text: str) -> str:
    """Classify an alert into exactly one of the six TRIAGE_BRANCHES keys."""
    classifier_system = (
        "You are a strict SOC alert classifier. Read the alert and reply "
        "with ONLY one of these exact labels, lowercase, nothing else: "
        "phishing, malware, lateral_movement, data_exfiltration, "
        "brute_force, false_positive."
    )
    label = ask_claude(classifier_system, alert_text, max_tokens=20).strip().lower()

    if label not in TRIAGE_BRANCHES:
        return "false_positive"
    return label


def run_adaptive_triage(alert_text: str) -> dict:
    """Classify the alert, then run the matching specialist playbook."""
    branch = classify_alert(alert_text)
    specialist_system = TRIAGE_BRANCHES[branch]
    answer = ask_claude(specialist_system, alert_text, max_tokens=500)
    return {"branch": branch, "answer": answer}




if __name__ == "__main__":
    #FIXED pipeline demo: overnight threat-intel digest
    OVERNIGHT_FEED = """\
Overnight threat-intel roundup (source: multiple ISAC feeds, CrowdStrike, Recorded Future):

1. New Cobalt Strike C2 infrastructure observed at IP 203.0.113.47,
   geolocated Singapore, ASN AS65000. Associated with recent financial-
   sector intrusions attributed to FIN-style actors.
2. Malware sample (SHA256 a1b2c3d4e5f6...9f) identified as an info-stealer
   targeting browser-stored credentials at asset-management firms.
3. Phishing domain "northgate-secure-login[.]com" registered 3 days ago,
   mimicking corporate SSO portals.
4. CVE-2026-31337: critical unauthenticated RCE in a widely-used VPN
   appliance; actively exploited in the wild per CISA advisory.
5. Suspicious outbound traffic pattern matching known market-data-feed
   exfiltration tooling, contacting IP 198.51.100.200.
"""

    ASSET_INVENTORY = """\
NorthGate Capital asset inventory (partial):
- research-analyst-laptop-01 through -12 (Windows 11, CrowdStrike Falcon agent)
- trading-prod-01, trading-prod-02 (Linux, order execution servers)
- market-data-relay-01 (ingests Reuters + Bloomberg feeds)
- VPN appliance: model AcmeVPN-5000, firmware 4.2.1 (matches CVE-2026-31337
  affected versions)
- Corporate SSO: login.northgatecapital.com (Okta-backed)
- No current usage of IP 198.51.100.200
"""

    digest = run_fixed_intel_digest(OVERNIGHT_FEED, ASSET_INVENTORY)

    print("=== FIXED: OVERNIGHT INTEL DIGEST ===")
    print("\n-- IoCs --")
    print(json.dumps(digest["iocs"], indent=2))
    print("\n-- Matches against NorthGate assets --")
    print(digest["matches"])
    print("\n-- Executive brief --")
    print(digest["exec_brief"])

    # ADAPTIVE pipeline demo: three different live alerts
    print("\n\n=== ADAPTIVE: ALERT TRIAGE ===")

    alerts = {
        "data_exfiltration (expected)": (
            "Alert ID: NG-2027-1142\n"
            "Severity: HIGH (pre-triage)\n"
            "Source: EDR (CrowdStrike Falcon)\n"
            "Time: 02:47 EST\n"
            "Asset: research-analyst-laptop-04 (owner: Maya Iyer, Sr. Equity Research)\n"
            "Event: Outbound transfer of 8.3 GB to external IP 203.0.113.47 "
            "(geolocation: Singapore, ASN: AS65000)\n"
            "Context: Transfer outside business hours; no active VPN session; "
            "owner's badge swipes show she left the office at 18:22 EST."
        ),
        "phishing (expected)": (
            "Alert ID: NG-2027-1150\n"
            "Severity: MEDIUM\n"
            "Source: Microsoft 365 Defender\n"
            "Event: User jsmith@northgatecapital.com reported a suspicious email "
            "impersonating IT support, requesting SSO credentials via a link to "
            "'northgate-secure-login[.]com'. User states they clicked the link "
            "but did not enter credentials before recognizing it was fake."
        ),
        "brute_force (expected)": (
            "Alert ID: NG-2027-1163\n"
            "Severity: HIGH\n"
            "Source: SIEM (Splunk)\n"
            "Event: 214 failed login attempts against the corporate VPN "
            "appliance for account 'rjones' from external IP 45.33.12.90 "
            "within a 10-minute window, followed by one successful login."
        ),
    }

    for label, alert_text in alerts.items():
        result = run_adaptive_triage(alert_text)
        print(f"\n--- Alert: {label} ---")
        print(f"Routed to branch: {result['branch']}")
        print(f"Specialist response:\n{result['answer']}")
