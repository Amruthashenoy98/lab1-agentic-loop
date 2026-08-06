from context import TicketContext


class PipelineGateError(Exception):
    pass


def gate_classification(ctx: TicketContext) -> None:
    if ctx.classification_complete():
        return

    missing = [
        name
        for name, value in (
            ("product_area", ctx.product_area),
            ("severity", ctx.severity),
            ("intent", ctx.intent),
        )
        if value is None
    ]
    raise PipelineGateError(
        f"Gate 1 (classification) failed: missing field(s) {missing}. "
        "Classification must be fully populated (product_area, severity, "
        "intent) before proceeding to the CRM Enricher. Rerun the Classifier."
    )


def gate_enrichment(ctx: TicketContext) -> None:
    if ctx.enrichment_complete():
        return

    missing = [
        name
        for name, value in (
            ("account_tier", ctx.account_tier),
            ("sla_tier", ctx.sla_tier),
        )
        if value is None
    ]
    raise PipelineGateError(
        f"Gate 2 (enrichment) failed: {missing} is None. "
        "account_tier and sla_tier must both be populated before proceeding "
        "to the Drafter. Rerun the CRM Enricher."
    )


def gate_draft(ctx: TicketContext) -> None:
    if ctx.draft_complete():
        return

    raise PipelineGateError(
        "Gate 3 (draft) failed: draft_response is None. "
        "A draft must exist before proceeding to the Validator. "
        "Rerun the Drafter."
    )
