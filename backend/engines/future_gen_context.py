"""
Resolve ancestor context and conversation excerpts for persona generation.

Walks the memory tree from a given self back to root, collecting:
- Ancestor summaries (one line per ancestor: name + goal + trade-off)
- Conversation excerpts (transcript entries where phase == "conversation")

This feeds into GenerationContext so deeper generations get richer context.
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.config.runtime import get_runtime_config

_runtime_fg_ctx = get_runtime_config().future_generation_context

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_ancestor_context(
    session_id: str,
    parent_self_id: str,
    storage_path: str,
    *,
    max_conversation_excerpts_per_ancestor: int = _runtime_fg_ctx.max_conversation_excerpts_per_ancestor,
    max_total_excerpts: int = _runtime_fg_ctx.max_total_excerpts,
    include_roles: list[str] | tuple[str, ...] = tuple(_runtime_fg_ctx.include_roles),
) -> tuple[str, list[str]]:
    """
    Walk from ``parent_self_id`` up to root, collecting ancestor summaries
    and conversation excerpts.

    Returns:
        (ancestor_summary, conversation_excerpts)

        ancestor_summary: one-sentence-per-ancestor narrative, oldest first.
            Example:
            "→ Self Who Took Singapore: optimized for acceleration, traded familiarity"
            "→ Self Who Found Community: optimized for belonging, traded career speed"

        conversation_excerpts: notable user ↔ self exchanges from
            ancestors' conversations, most recent first.
    """
    session_dir = Path(storage_path) / session_id
    nodes_dir = session_dir / "memory" / "nodes"

    # --- Build lookup tables ---
    nodes_by_self_id: dict[str, dict] = {}
    nodes_by_id: dict[str, dict] = {}
    for node_file in nodes_dir.glob("*.json"):
        node = json.loads(node_file.read_text(encoding="utf-8"))
        nodes_by_id[node["id"]] = node
        self_card = node.get("selfCard")
        if self_card:
            nodes_by_id[node["id"]] = node
            sid = self_card.get("id")
            if sid:
                nodes_by_self_id[sid] = node

    # --- Walk from parent to root ---
    ancestor_chain: list[dict] = []  # oldest → newest
    visited: set[str] = set()

    current_node = nodes_by_self_id.get(parent_self_id)
    while current_node and current_node["id"] not in visited:
        visited.add(current_node["id"])
        self_card = current_node.get("selfCard")
        if self_card:
            ancestor_chain.append(self_card)
        parent_id = current_node.get("parentId")
        if parent_id and parent_id in nodes_by_id:
            current_node = nodes_by_id[parent_id]
        else:
            break

    # Reverse to get oldest-first (root→parent)
    ancestor_chain.reverse()

    # --- Build summary (skip the immediate parent — caller already has it) ---
    summary_lines: list[str] = []
    # Include all ancestors except the last one (which is the parent_self itself)
    for card in ancestor_chain[:-1] if len(ancestor_chain) > 1 else []:
        name = card.get("name", "Unknown")
        goal = card.get("optimizationGoal", card.get("optimization_goal", "?"))
        trade = card.get("tradeOff", card.get("trade_off", "?"))
        summary_lines.append(f"→ {name}: optimized for {goal}, traded {trade}")

    ancestor_summary = "\n".join(summary_lines)

    # --- Collect conversation excerpts from transcript ---
    conversation_excerpts: list[str] = []
    transcript_file = session_dir / "transcript.json"
    if transcript_file.exists():
        allowed_roles = {
            str(role).strip().lower()
            for role in include_roles
            if isinstance(role, str) and role.strip()
        } or {"user", "assistant", "memory"}

        transcript: list[dict] = json.loads(
            transcript_file.read_text(encoding="utf-8")
        )
        # Gather names of ancestors for filtering
        ancestor_names = {
            card.get("name") for card in ancestor_chain if card.get("name")
        }

        # Filter to conversation-phase entries involving ancestors
        convo_entries = [
            entry
            for entry in transcript
            if entry.get("phase") == "conversation"
            and entry.get("selfName") in ancestor_names
            and str(entry.get("role", "")).strip().lower() in allowed_roles
        ]

        # Take most recent entries, grouped by ancestor.
        # Pass 1 prefers user/assistant turns so narrative context is not crowded out
        # by transcript-memory entries. Pass 2 backfills remaining slots.
        seen_per_ancestor: dict[str, int] = {}
        selected_ids: set[int] = set()
        preferred_roles = {"user", "assistant"} & allowed_roles

        def _collect_pass(*, roles: set[str] | None) -> None:
            for entry in reversed(convo_entries):
                if len(conversation_excerpts) >= max_total_excerpts:
                    break
                entry_id = id(entry)
                if entry_id in selected_ids:
                    continue
                role = str(entry.get("role", "?")).strip().lower()
                if roles is not None and role not in roles:
                    continue

                name = entry.get("selfName", "")
                seen_per_ancestor.setdefault(name, 0)
                if seen_per_ancestor[name] >= max_conversation_excerpts_per_ancestor:
                    continue
                content = entry.get("content", "")
                conversation_excerpts.append(f"[{role} ↔ {name}]: {content}")
                seen_per_ancestor[name] += 1
                selected_ids.add(entry_id)

        if preferred_roles:
            _collect_pass(roles=preferred_roles)
        _collect_pass(roles=allowed_roles - preferred_roles if preferred_roles else None)

        # Reverse back to chronological order
        conversation_excerpts.reverse()

    return ancestor_summary, conversation_excerpts


def collect_sibling_names(
    session_data: dict,
    parent_key: str,
) -> list[str]:
    """
    Collect names of selves already generated under the same parent.

    Used to inject into the prompt so the LLM avoids duplicate themes.
    """
    full = session_data.get("futureSelvesFull", {})
    child_ids = session_data.get("explorationPaths", {}).get(parent_key, [])
    return [
        full[cid].get("name", "")
        for cid in child_ids
        if cid in full
    ]
