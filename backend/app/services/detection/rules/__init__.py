from app.services.detection.rules.stalled_invoice import stalled_invoice_rule
from app.services.detection.rules.stale_lead import stale_lead_rule
from app.services.detection.rules.recovery_candidate import recovery_candidate_rule
from app.services.detection.rules.sequence_eligible import sequence_eligible_rule

REGISTRY = [
    stalled_invoice_rule,
    stale_lead_rule,
    recovery_candidate_rule,
    sequence_eligible_rule,
]

__all__ = [
    "REGISTRY",
    "stalled_invoice_rule",
    "stale_lead_rule",
    "recovery_candidate_rule",
    "sequence_eligible_rule",
]
