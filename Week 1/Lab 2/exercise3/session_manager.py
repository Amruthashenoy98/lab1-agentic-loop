"""
session_manager.py

Session-state primitives for Sentinel investigations: save/resume, fork, and
summarize. A session is a plain dict -- {id, parent_id, messages, summary} --
stored as a JSON file under ./sessions/. Any analyst can open the file and
read exactly what the agent remembers.

"""

import os
import json
import uuid

import anthropic

client = anthropic.Anthropic()

SUMMARY_MODEL = os.environ["ANTHROPIC_MODEL"]


SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")


# ---------------------------------------------------------------------------
# Core primitives
# ---------------------------------------------------------------------------

def new_session() -> dict:
    """Return a fresh session dict with a new short id, no parent, and empty
    messages/summary."""
    return {
        "id": uuid.uuid4().hex[:6],
        "parent_id": None,
        "messages": [],
        "summary": "",
    }


def add_user(session: dict, text: str) -> None:
    """Append a user turn to session['messages']."""
    session["messages"].append({"role": "user", "content": text})


def add_assistant(session: dict, text: str) -> None:
    """Append an assistant turn to session['messages']."""
    session["messages"].append({"role": "assistant", "content": text})


def save_session(session: dict) -> str:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    path = os.path.join(SESSIONS_DIR, f"{session['id']}.json")
    with open(path, "w") as f:
        json.dump(session, f, indent=2)
    print(f"[save_session] Saved {len(session['messages'])} messages to {path}")
    return path


def resume_session(session_id: str) -> dict:
    path = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No session found with id '{session_id}' at {path}. "
            "Check the id or confirm the session was saved."
        )
    with open(path, "r") as f:
        session = json.load(f)
    print(f"[resume_session] Resumed session '{session_id}' with "
          f"{len(session['messages'])} messages.")
    return session


def fork_session(parent: dict) -> dict:
    child = new_session()
    child["messages"] = list(parent["messages"])  # copy, never alias
    child["parent_id"] = parent["id"]
    child["summary"] = parent["summary"]
    print(f"[fork_session] Forked '{parent['id']}' -> new branch '{child['id']}' "
          f"with {len(child['messages'])} inherited messages.")
    return child


def summarize_session(session: dict, keep_recent: int = 2) -> dict:
    messages = session["messages"]
    if len(messages) <= keep_recent:
        print("[summarize_session] Not enough messages to summarize; "
              "leaving session unchanged.")
        return session

    older = messages[:-keep_recent]
    recent = messages[-keep_recent:]

    transcript = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in older
    )

    system_prompt = (
        "You are compressing a security investigation's message history into "
        "a structured digest for handoff between shifts. Output EXACTLY three "
        "sections, in this order, with these exact headers:\n"
        "DECISIONS:\n"
        "FACTS:\n"
        "OPEN:\n\n"
        "DECISIONS lists actions taken or decided (e.g. quarantine, escalation, "
        "legal hold). FACTS lists concrete evidence gathered. OPEN lists "
        "unresolved questions or next steps.\n\n"
        "CRITICAL: never drop or vaguely paraphrase concrete values -- alert "
        "IDs, hostnames, IP addresses, file hashes, usernames, ticket/hold "
        "IDs, and timestamps must all be preserved exactly as given, even "
        "when summarizing heavily."
    )

    response = client.messages.create(
        model=SUMMARY_MODEL,
        max_tokens=800,
        system=system_prompt,
        messages=[{"role": "user", "content": transcript}],
    )
    digest = response.content[0].text.strip()

    session["summary"] = digest
    session["messages"] = recent

    print(f"[summarize_session] Compressed {len(older)} older messages into "
          f"a digest; kept the last {len(recent)} messages verbatim.")
    return session

# Demo


if __name__ == "__main__":
    print("=" * 70)
    print("DEMO 1 -- Save & Resume across a shift change")
    print("=" * 70)

    day1 = new_session()
    add_user(
        day1,
        "Alert NG-2027-1142: EDR flagged an 8.3 GB outbound transfer from "
        "research-analyst-laptop-04 (owner Maya Iyer) to external IP "
        "203.0.113.47 (Singapore, ASN AS65000), outside business hours, no "
        "active VPN session.",
    )
    add_assistant(
        day1,
        "Sarah Chen (Tier-1, night shift), 02:47 EST: Ran SIEM query "
        "source_ip=203.0.113.47 -- 1 match, first contact at 01:58 EST. "
        "Badge swipe data shows Maya Iyer left the office at 18:22 EST, "
        "well before the transfer. Leading hypotheses: (1) compromised "
        "credentials used off-hours by an external actor, (2) insider "
        "exfiltration staged before she left. Handing off to Tier-2 at "
        "shift change.",
    )
    saved_path = save_session(day1)
    day1_id = day1["id"]

    # Simulate the shift ending -- the in-memory session object is gone.
    del day1
    print("(Sarah's shift ends -- in-memory session object deleted.)\n")

    print("Day 2, 08:00 EST -- Mike Torres (Tier-2 lead) resumes the case:")
    resumed = resume_session(day1_id)
    for m in resumed["messages"]:
        print(f"  [{m['role']}] {m['content'][:90]}...")

    print("\n" + "=" * 70)
    print("DEMO 2 -- Fork into parallel hypotheses")
    print("=" * 70)

    branch_a = fork_session(resumed)  # insider threat
    add_user(
        branch_a,
        "Branch A -- insider threat: pull Maya Iyer's HR record and check "
        "for a recent departure notice or performance flag.",
    )
    add_assistant(
        branch_a,
        "HR record check: no departure notice on file. No performance "
        "flags in the last 12 months. Insider-threat hypothesis weakened "
        "but not ruled out -- credentials may still have been used by "
        "someone else.",
    )
    branch_a_path = save_session(branch_a)

    branch_b = fork_session(resumed)  # external APT
    add_user(
        branch_b,
        "Branch B -- external APT: pull a memory image and process tree "
        "from research-analyst-laptop-04 and check for persistence "
        "mechanisms.",
    )
    add_assistant(
        branch_b,
        "Memory image acquired (hash: 9f8e7d6c5b4a...). Process tree shows "
        "an unsigned binary masquerading as a system update service, with "
        "a scheduled-task persistence mechanism. Strongly consistent with "
        "external APT compromise, not insider action.",
    )
    branch_b_path = save_session(branch_b)

    print(f"\nBranch A id: {branch_a['id']}, parent_id: {branch_a['parent_id']}")
    print(f"Branch B id: {branch_b['id']}, parent_id: {branch_b['parent_id']}")
    print(f"Both share parent id: {branch_a['parent_id'] == branch_b['parent_id'] == resumed['id']}")
    print(f"Branches diverge after fork: "
          f"{len(branch_a['messages'])} vs {len(branch_b['messages'])} messages, "
          f"different content after the shared prefix.")

    print("\n" + "=" * 70)
    print("DEMO 3 -- Summarize a long evidence-collection history")
    print("=" * 70)

    long_session = new_session()
    evidence_turns = [
        ("user", "Continue evidence collection on NG-2027-1142."),
        ("assistant", "Pulled full packet capture for the 02:47 EST outbound "
                       "transfer window; saved as pcap-ng2027-1142-01.pcap."),
        ("user", "Acquire a memory image of research-analyst-laptop-04."),
        ("assistant", "Memory image acquired. SHA256 hash: "
                       "9f8e7d6c5b4a3928374659abcdee1122334455667788990011223344."),
        ("user", "Decision: quarantine research-analyst-laptop-04 pending analysis."),
        ("assistant", "Quarantine executed via EDR at 08:14 EST. Host isolated "
                       "from network. Confirmed via CrowdStrike console."),
        ("user", "Legal has been notified given possible client-data exposure."),
        ("assistant", "Legal hold opened. Hold ID: LH-2027-0091. Custodian: "
                       "Maya Iyer. Scope: all local files and email from "
                       "2027-01-01 to present."),
        ("user", "Any update on the external IP 203.0.113.47?"),
        ("assistant", "IP 203.0.113.47 confirmed added to firewall deny-list. "
                       "WHOIS shows ASN AS65000, no reverse DNS. Flagged to "
                       "threat-intel team for further attribution."),
    ]
    for role, text in evidence_turns:
        if role == "user":
            add_user(long_session, text)
        else:
            add_assistant(long_session, text)

    print(f"Built a session with {len(long_session['messages'])} messages.\n")

    summarized = summarize_session(long_session, keep_recent=2)

    print("\n-- Resulting summary (session['summary']) --")
    print(summarized["summary"])

    print(f"\n-- Remaining messages after summarization "
          f"({len(summarized['messages'])} kept verbatim) --")
    for m in summarized["messages"]:
        print(f"  [{m['role']}] {m['content'][:90]}...")
