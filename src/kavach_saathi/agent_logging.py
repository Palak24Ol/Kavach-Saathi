from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from kavach_saathi.db.models import AgentLog


def log_agent_call(
    session: Session,
    *,
    agent_name: str,
    entity_type: str,
    entity_id: str,
    confidence: int,
    latency_ms: int,
    output_json: dict[str, Any],
    input_ref: str | None = None,
    provider: str | None = None,
    run_id: str | None = None,
) -> AgentLog:
    """Persist one real, queryable agent decision.

    Every agent call must go through this so a judge can open `agent_logs` and see
    exactly why an agent made a decision: which provider served it, what it was given
    (`input_ref`), what it returned (`output_json`), how confident it was, and how long
    it took (`latency_ms`). This is Section 4's `agent_logs` table contract.
    """
    entry = AgentLog(
        agent_name=agent_name,
        entity_type=entity_type,
        entity_id=entity_id,
        input_ref=input_ref,
        output_json=output_json,
        confidence=confidence,
        provider=provider,
        latency_ms=latency_ms,
        run_id=run_id,
    )
    session.add(entry)
    session.flush()
    return entry
