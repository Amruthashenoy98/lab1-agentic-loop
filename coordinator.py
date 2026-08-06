"""
coordinator.py

Plain-Python orchestrator for the support-ticket triage pipeline.
"""

from subagents import (
    run_classifier,
    run_crm_enricher,
    run_drafter,
    run_validator,
)



TICKET = (
    "Subject: Production API returning 500 errors since this morning\n\n"
    "Hi, since around 9am our integration has been getting 500 Internal "
    "Server Error responses on roughly 1 in 5 requests to the /v1/orders "
    "endpoint. This is blocking checkout for our customers. We are on the "
    "Enterprise plan and this is a critical outage for us. Please advise ASAP."
)

CUSTOMER_EMAIL = "ops-lead@acmecorp.com"


def run_pipeline(ticket: str, customer_email: str) -> None:
    #Classifier
    classification = run_classifier(ticket)
    print("=== CLASSIFIER ===")
    print(classification)
    print()

    #CRM Enricher 
    crm = run_crm_enricher(customer_email, classification)
    print("=== CRM ENRICHER ===")
    print(crm)
    print()

    #Drafter (needs the ticket, classification, and CRM data)
    draft = run_drafter(ticket, classification, crm)
    print("=== DRAFTER ===")
    print(draft)
    print()

    #Validator (needs the draft, classification, and CRM data)
    validation = run_validator(draft, classification, crm)
    print("=== VALIDATOR ===")
    print(validation)
    print()


if __name__ == "__main__":
    run_pipeline(TICKET, CUSTOMER_EMAIL)