#!/usr/bin/env python3
"""Customer-input financial value calculator.

No dollar value is asserted without explicit customer inputs. Locked HELIXNID evidence
may be used as an operational rate, but every cost and intervention assumption remains
visible in the output.
"""
from __future__ import annotations

from typing import Any

LOCKED_IMPROVED_RATE = 0.8513069066989787
LOCKED_TOP10_LATE_RECALL = 0.42903
LOCKED_TOP10_FLAG_RATE = 0.10


def calculate(payload: dict[str, Any]) -> dict[str, Any]:
    shipments = max(0.0, float(payload.get("shipment_volume", 0)))
    support_rate = max(0.0, float(payload.get("support_contact_rate", 0)))
    support_cost = max(0.0, float(payload.get("support_contact_cost", 0)))
    refund_rate = max(0.0, float(payload.get("refund_or_replacement_rate", 0)))
    refund_cost = max(0.0, float(payload.get("refund_or_replacement_cost", 0)))
    late_comp_rate = max(0.0, float(payload.get("late_compensation_rate", 0)))
    late_comp_cost = max(0.0, float(payload.get("late_compensation_cost", 0)))
    intervention_success = min(1.0, max(0.0, float(payload.get("intervention_success_rate", 0))))
    use_locked = bool(payload.get("use_locked_improved_rate", True))
    improved_rate = LOCKED_IMPROVED_RATE if use_locked else min(
        1.0, max(0.0, float(payload.get("improved_shipment_rate", 0)))
    )

    eligible = shipments * improved_rate
    affected = eligible * intervention_success
    support_contacts_avoided = affected * support_rate
    refunds_avoided = affected * refund_rate
    compensation_avoided = affected * late_comp_rate
    support_value = support_contacts_avoided * support_cost
    refund_value = refunds_avoided * refund_cost
    compensation_value = compensation_avoided * late_comp_cost
    total = support_value + refund_value + compensation_value

    flagged_for_proactive_work = shipments * LOCKED_TOP10_FLAG_RATE
    late_shipments_captured_equivalent = shipments * LOCKED_TOP10_LATE_RECALL * float(
        payload.get("observed_late_rate", 0)
    )

    return {
        "shipment_volume": shipments,
        "assumptions": {
            "improved_shipment_rate": improved_rate,
            "improved_rate_source": "locked Olist replay" if use_locked else "customer supplied",
            "intervention_success_rate": intervention_success,
            "support_contact_rate": support_rate,
            "support_contact_cost": support_cost,
            "refund_or_replacement_rate": refund_rate,
            "refund_or_replacement_cost": refund_cost,
            "late_compensation_rate": late_comp_rate,
            "late_compensation_cost": late_comp_cost,
        },
        "operational_projection": {
            "shipments_with_more_accurate_prediction": eligible,
            "shipments_where_action_succeeds": affected,
            "top_10pct_shipments_flagged": flagged_for_proactive_work,
            "late_shipments_captured_equivalent": late_shipments_captured_equivalent,
        },
        "financial_projection": {
            "support_contacts_avoided": support_contacts_avoided,
            "support_value": support_value,
            "refunds_or_replacements_avoided": refunds_avoided,
            "refund_or_replacement_value": refund_value,
            "late_compensations_avoided": compensation_avoided,
            "late_compensation_value": compensation_value,
            "total_projected_value": total,
            "projected_value_per_shipment": total / shipments if shipments else 0.0,
        },
        "claim_boundary": "This is a transparent scenario calculation, not a guaranteed savings claim. Dollar amounts are entirely determined by customer-supplied costs, rates, and intervention success.",
    }
