from context import TicketContext
from gates import (
    PipelineGateError,
    gate_classification,
    gate_enrichment,
    gate_draft,
)
from subagents import (
    run_classifier,
    run_crm_enricher,
    run_drafter,
    run_validator,
)


TICKET_ID = "T-1001"

RAW_TICKET = (
    "Subject: Production API returning 500 errors since this morning\n\n"
    "Hi, since around 9am our integration has been getting 500 Internal "
    "Server Error responses on roughly 1 in 5 requests to the /v1/orders "
    "endpoint. This is blocking checkout for our customers. We are on the "
    "Enterprise plan and this is a critical outage for us. Please advise ASAP."
)

CUSTOMER_EMAIL = "ops-lead@acmecorp.com"


def run_pipeline(ctx: TicketContext) -> TicketContext:
    classification = run_classifier(ctx.raw_ticket)
    ctx.product_area = classification["product_area"]
    ctx.severity = classification["severity"]
    ctx.intent = classification["intent"]
    print("=== CLASSIFIER ===")
    print(classification)
    print()

    
    ctx.severity = None
    print(">>> SABOTAGE: ctx.severity forcibly reset to None before Gate 1 <<<\n")

    
    gate_classification(ctx)
    print("Gate 1 passed: classification complete.\n")

    
    crm = run_crm_enricher(
        ctx.customer_email,
        {
            "product_area": ctx.product_area,
            "severity": ctx.severity,
            "intent": ctx.intent,
        },
    )
    ctx.account_tier = crm["account_tier"]
    ctx.sla_tier = crm["sla_tier"]
    ctx.account_manager = crm["account_manager"]
    print("=== CRM ENRICHER ===")
    print(crm)
    print()

    
    gate_enrichment(ctx)
    print("Gate 2 passed: enrichment complete.\n")

    
    draft = run_drafter(
        ctx.raw_ticket,
        {
            "product_area": ctx.product_area,
            "severity": ctx.severity,
            "intent": ctx.intent,
        },
        {
            "account_tier": ctx.account_tier,
            "sla_tier": ctx.sla_tier,
            "account_manager": ctx.account_manager,
        },
    )
    ctx.draft_response = draft
    print("=== DRAFTER ===")
    print(draft)
    print()

    
    gate_draft(ctx)
    print("Gate 3 passed: draft complete.\n")

    
    validation = run_validator(
        ctx.draft_response,
        {
            "product_area": ctx.product_area,
            "severity": ctx.severity,
            "intent": ctx.intent,
        },
        {
            "account_tier": ctx.account_tier,
            "sla_tier": ctx.sla_tier,
            "account_manager": ctx.account_manager,
        },
    )
    ctx.validation_result = validation
    print("=== VALIDATOR ===")
    print(validation)
    print()

    return ctx


if __name__ == "__main__":
    ctx = TicketContext(
        ticket_id=TICKET_ID,
        raw_ticket=RAW_TICKET,
        customer_email=CUSTOMER_EMAIL,
    )

    try:
        ctx = run_pipeline(ctx)
        print("=== FINAL CONTEXT ===")
        print(ctx)
    except PipelineGateError as e:
        print(f"[PIPELINE BLOCKED] {e}")
