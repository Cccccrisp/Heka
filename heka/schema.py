"""Schemas and validation at Heka's trust boundary.

The LLM may suggest structure, but this module decides what is safe to store.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


DEFAULT_MODEL: dict[str, Any] = {
    "version": 1,
    "updated_at": None,
    "confirmed_dimensions": {},
    "hypotheses": [],
    "history_note": "Only user-confirmed proposals may change confirmed_dimensions.",
}


# Local models occasionally return a plain-language synonym even when the
# prompt enumerates the storage vocabulary. These are safe, lossless aliases;
# anything outside this narrow map still fails closed at the trust boundary.
FACT_CATEGORY_ALIASES = {
    "behavior": "action",
    "behaviour": "action",
    "decision": "choice",
    "feeling": "emotion",
    "sentiment": "emotion",
    "statement": "expression",
    "belief": "expression",
    "event": "other",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_model() -> dict[str, Any]:
    model = deepcopy(DEFAULT_MODEL)
    model["updated_at"] = utc_now()
    return model


def _bounded_number(value: Any, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} must be a number")
    value = float(value)
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return value


def validate_analysis(payload: Any) -> dict[str, Any]:
    """Validate untrusted model output before it crosses into local storage."""
    if not isinstance(payload, dict):
        raise ValueError("analysis must be a JSON object")
    trace = payload.get("trace")
    proposal = payload.get("proposal")
    if not isinstance(trace, dict) or not isinstance(proposal, dict):
        raise ValueError("analysis must contain trace and proposal objects")

    required_trace = ("event_type", "observable_facts", "candidate_interpretations", "confidence")
    if any(key not in trace for key in required_trace):
        raise ValueError("trace is missing required fields")
    if not isinstance(trace["event_type"], str) or not trace["event_type"].strip():
        raise ValueError("trace.event_type must be non-empty text")
    if not isinstance(trace["observable_facts"], list) or not trace["observable_facts"]:
        raise ValueError("trace.observable_facts must be a non-empty list")
    normalized_facts = []
    for item in trace["observable_facts"]:
        if isinstance(item, str):  # backward compatibility for earlier traces and mock mode
            item = {"statement": item, "category": "other", "source_quote": "", "confidence": trace["confidence"]}
        if not isinstance(item, dict) or not isinstance(item.get("statement"), str) or not item["statement"].strip():
            raise ValueError("every observable fact needs a statement")
        category = FACT_CATEGORY_ALIASES.get(item.get("category", "other"), item.get("category", "other"))
        if category not in {"choice", "action", "emotion", "context", "outcome", "expression", "other"}:
            # A category supports filtering only. The source quote and fact
            # statement are still validated below, so preserve the evidence
            # and file an unfamiliar taxonomy under the explicit catch-all.
            category = "other"
        if not isinstance(item.get("source_quote", ""), str):
            raise ValueError("fact source_quote must be text")
        item["category"] = category
        item["source_quote"] = item.get("source_quote", "")
        item["confidence"] = _bounded_number(item.get("confidence", trace["confidence"]), "fact.confidence")
        normalized_facts.append(item)
    trace["observable_facts"] = normalized_facts

    if not isinstance(trace["candidate_interpretations"], list):
        raise ValueError("trace.candidate_interpretations must be a list")
    normalized_interpretations = []
    for item in trace["candidate_interpretations"]:
        if isinstance(item, str):
            item = {"statement": item, "based_on_facts": [], "missing_information": "", "confidence": trace["confidence"]}
        if not isinstance(item, dict) or not isinstance(item.get("statement"), str) or not item["statement"].strip():
            raise ValueError("every candidate interpretation needs a statement")
        indices = item.get("based_on_facts", [])
        if not isinstance(indices, list) or not all(isinstance(index, int) and 0 <= index < len(normalized_facts) for index in indices):
            raise ValueError("interpretation fact indexes are invalid")
        if not isinstance(item.get("missing_information", ""), str):
            raise ValueError("interpretation missing_information must be text")
        item["based_on_facts"] = indices
        item["missing_information"] = item.get("missing_information", "")
        item["confidence"] = _bounded_number(item.get("confidence", trace["confidence"]), "interpretation.confidence")
        normalized_interpretations.append(item)
    trace["candidate_interpretations"] = normalized_interpretations
    decision = trace.get("decision")
    if decision is not None:
        if not isinstance(decision, dict) or not isinstance(decision.get("question"), str):
            raise ValueError("decision must have a question")
        if decision.get("stage", "considering") not in {"considering", "made", "revisited"}:
            raise ValueError("decision stage is invalid")
        if not isinstance(decision.get("selected_option", ""), str):
            raise ValueError("decision selected_option must be text")
        if not isinstance(decision.get("options", []), list) or not all(isinstance(option, str) for option in decision["options"]):
            raise ValueError("decision options must be text")
        reasons = decision.get("reason_fact_indices", [])
        if not isinstance(reasons, list) or not all(isinstance(index, int) and 0 <= index < len(normalized_facts) for index in reasons):
            raise ValueError("decision reason fact indexes are invalid")
        if decision.get("reversibility", "unknown") not in {"high", "medium", "low", "unknown"}:
            raise ValueError("decision reversibility is invalid")
        decision["stage"] = decision.get("stage", "considering")
        decision["selected_option"] = decision.get("selected_option", "")
        decision["reason_fact_indices"] = reasons
        decision["reversibility"] = decision.get("reversibility", "unknown")
    for name, allowed_status in (("actions", {"done", "planned", "stopped", "unknown"}), ("emotions", {"low", "medium", "high", "unknown"})):
        values = trace.get(name, [])
        if not isinstance(values, list):
            raise ValueError(f"trace.{name} must be a list")
        for item in values:
            if not isinstance(item, dict) or not isinstance(item.get("statement", item.get("label")), str):
                raise ValueError(f"every {name[:-1]} needs text")
            if not isinstance(item.get("source_quote", ""), str):
                raise ValueError(f"{name[:-1]} source_quote must be text")
            field = "status" if name == "actions" else "intensity"
            if item.get(field, "unknown") not in allowed_status:
                raise ValueError(f"{name[:-1]} {field} is invalid")
            item[field] = item.get(field, "unknown")
            item["source_quote"] = item.get("source_quote", "")
    trace["actions"] = trace.get("actions", [])
    trace["emotions"] = trace.get("emotions", [])
    trace["confidence"] = _bounded_number(trace["confidence"], "trace.confidence")
    trace.setdefault("tags", [])
    if not isinstance(trace["tags"], list) or not all(isinstance(item, str) for item in trace["tags"]):
        raise ValueError("trace.tags must be a list of text")

    required_proposal = ("kind", "reason", "evidence", "confidence", "needs_user_confirmation")
    if any(key not in proposal for key in required_proposal):
        raise ValueError("proposal is missing required fields")
    if proposal["kind"] not in {"dimension_update", "hypothesis", "no_change"}:
        raise ValueError("proposal.kind is invalid")
    if not isinstance(proposal["reason"], str) or not isinstance(proposal["evidence"], list):
        raise ValueError("proposal reason/evidence is invalid")
    if not all(isinstance(item, str) for item in proposal["evidence"]):
        raise ValueError("proposal.evidence must be a list of text")
    proposal["confidence"] = _bounded_number(proposal["confidence"], "proposal.confidence")
    if proposal["needs_user_confirmation"] is not True:
        raise ValueError("all proposals must require user confirmation")
    if not isinstance(proposal.get("scope", "当前记录的场景"), str):
        raise ValueError("proposal scope must be text")
    proposal["scope"] = proposal.get("scope", "当前记录的场景")

    if proposal["kind"] == "dimension_update":
        if not isinstance(proposal.get("dimension"), str) or not proposal["dimension"].strip():
            raise ValueError("dimension_update requires a dimension")
        proposal["suggested_value"] = _bounded_number(proposal.get("suggested_value"), "proposal.suggested_value")
    return {"trace": trace, "proposal": proposal}


def apply_confirmed_proposal(model: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """Create a new model version after an explicit user approval."""
    next_model = deepcopy(model)
    next_model["version"] = int(next_model.get("version", 0)) + 1
    next_model["updated_at"] = utc_now()
    kind = proposal["kind"]
    if kind == "dimension_update":
        dimension = proposal["dimension"]
        next_model.setdefault("confirmed_dimensions", {})[dimension] = {
            "value": proposal["suggested_value"],
            "confidence": proposal["confidence"],
            "scope": proposal["scope"],
            "evidence": proposal["evidence"],
            "confirmed_at": next_model["updated_at"],
        }
    elif kind == "hypothesis":
        next_model.setdefault("hypotheses", []).append({
            "statement": proposal.get("statement", proposal["reason"]),
            "confidence": proposal["confidence"],
            "evidence": proposal["evidence"],
            "next_validation": proposal.get("next_validation", "Collect another relevant trace before treating this as stable."),
            "scope": proposal["scope"],
            "added_at": next_model["updated_at"],
        })
    return next_model
