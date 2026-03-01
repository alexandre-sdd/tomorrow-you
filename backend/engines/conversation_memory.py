from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

from backend.config.runtime import get_runtime_config

_runtime = get_runtime_config().conversation_memory


def record_conversation_turn_and_memory(
    *,
    session_id: str,
    storage_root: str | Path,
    branch_name: str,
    self_id: str | None,
    self_name: str | None,
    user_text: str,
    assistant_text: str,
) -> list[str]:
    """
    Persist a full conversation turn and extracted user insights.

    Writes:
    - transcript entries (user + assistant + memory insights)
    - current branch node updates (facts + notes)
    """
    if not _runtime.enabled:
        return []

    cleaned_user = user_text.strip()
    cleaned_assistant = assistant_text.strip()
    if not cleaned_user or not cleaned_assistant:
        return []

    session_dir = Path(storage_root) / session_id
    insights = extract_key_elements(cleaned_user)
    now = time.time()

    _append_transcript_entries(
        session_dir=session_dir,
        branch_name=branch_name,
        self_id=self_id,
        self_name=self_name,
        user_text=cleaned_user,
        assistant_text=cleaned_assistant,
        insights=insights,
        timestamp=now,
    )
    _update_branch_node_memory(
        session_dir=session_dir,
        branch_name=branch_name,
        insights=insights,
        timestamp=now,
    )
    return insights


def extract_key_elements(user_text: str) -> list[str]:
    """
    Lightweight, deterministic insight extraction from user text.

    This avoids adding extra model latency/cost while still capturing stable
    branching signals (relationship, values, fears, dreams, trade-off tension).
    """
    text = " ".join(user_text.strip().split())
    if len(text) < _runtime.min_message_length_for_extraction:
        return []

    sentence = _best_sentence(text)
    lowered = text.lower()

    patterns: list[tuple[str, tuple[str, ...], str]] = [
        (
            "relationship",
            ("wife", "husband", "partner", "marriage", "relationship"),
            "Relationship concern",
        ),
        (
            "dream",
            ("dream", "aspiration", "goal", "vision", "purpose", "hope"),
            "Aspirational goal",
        ),
        (
            "fear",
            ("afraid", "fear", "scared", "anxious", "worry", "regret"),
            "Fear/regret signal",
        ),
        (
            "value",
            ("value", "important", "priority", "matters", "family", "stability"),
            "Core value emphasis",
        ),
        (
            "tradeoff",
            ("torn", "conflicted", "but", "however", "trade-off", "balance"),
            "Trade-off tension",
        ),
    ]

    insights: list[str] = []
    used_labels: set[str] = set()
    for label, keywords, title in patterns:
        if label in used_labels:
            continue
        if any(keyword in lowered for keyword in keywords):
            insights.append(f"{title}: {sentence}")
            used_labels.add(label)
        if len(insights) >= _runtime.max_insights_per_turn:
            break

    return _dedupe_keep_order(insights)


def _best_sentence(text: str) -> str:
    parts = [p.strip() for p in re.split(r"[.!?]+", text) if p.strip()]
    candidate = parts[0] if parts else text
    if len(candidate) > 220:
        return candidate[:217].rstrip() + "..."
    return candidate


def _append_transcript_entries(
    *,
    session_dir: Path,
    branch_name: str,
    self_id: str | None,
    self_name: str | None,
    user_text: str,
    assistant_text: str,
    insights: list[str],
    timestamp: float,
) -> None:
    transcript_path = session_dir / "transcript.json"
    transcript = _load_json_list(transcript_path)

    # Idempotency guard: do not append duplicate final user+assistant pair.
    if len(transcript) >= 2:
        prev_user = transcript[-2]
        prev_assistant = transcript[-1]
        if (
            prev_user.get("phase") == "conversation"
            and prev_user.get("role") == "user"
            and prev_user.get("content") == user_text
            and prev_user.get("selfId") == self_id
            and prev_assistant.get("phase") == "conversation"
            and prev_assistant.get("role") == "assistant"
            and prev_assistant.get("content") == assistant_text
            and prev_assistant.get("selfId") == self_id
        ):
            return

    entries: list[dict] = []
    entries.append(
        _new_transcript_entry(
            role="user",
            content=user_text,
            self_name=self_name,
            self_id=self_id,
            branch_name=branch_name,
            timestamp=timestamp,
        )
    )
    entries.append(
        _new_transcript_entry(
            role="assistant",
            content=assistant_text,
            self_name=self_name,
            self_id=self_id,
            branch_name=branch_name,
            timestamp=timestamp,
        )
    )
    for insight in insights:
        entries.append(
            _new_transcript_entry(
                role="memory",
                content=f"Key signal: {insight}",
                self_name=self_name,
                self_id=self_id,
                branch_name=branch_name,
                timestamp=timestamp,
            )
        )

    start_turn = len(transcript) + 1
    for idx, entry in enumerate(entries):
        entry["turn"] = start_turn + idx
        transcript.append(entry)

    if len(transcript) > _runtime.max_transcript_entries:
        transcript = transcript[-_runtime.max_transcript_entries :]

    transcript_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")


def _new_transcript_entry(
    *,
    role: str,
    content: str,
    self_name: str | None,
    self_id: str | None,
    branch_name: str,
    timestamp: float,
) -> dict:
    return {
        "id": f"te_{uuid.uuid4().hex[:12]}",
        "turn": 0,
        "phase": "conversation",
        "role": role,
        "selfName": self_name,
        "selfId": self_id,
        "branchName": branch_name,
        "content": content,
        "timestamp": timestamp,
    }


def _update_branch_node_memory(
    *,
    session_dir: Path,
    branch_name: str,
    insights: list[str],
    timestamp: float,
) -> None:
    if not insights:
        return

    branch_path = session_dir / "memory" / "branches.json"
    branches = _load_json_list(branch_path)
    head_node_id: str | None = None
    for branch in branches:
        if isinstance(branch, dict) and branch.get("name") == branch_name:
            node_id = branch.get("headNodeId")
            if isinstance(node_id, str) and node_id:
                head_node_id = node_id
                break
    if not head_node_id:
        return

    node_path = session_dir / "memory" / "nodes" / f"{head_node_id}.json"
    if not node_path.exists():
        return
    node = _load_json_dict(node_path)

    notes = list(node.get("notes") or [])
    facts = list(node.get("facts") or [])

    note_prefix = "User signal: "
    for insight in insights:
        note = f"{note_prefix}{insight}"
        if note not in notes:
            notes.append(note)

        if not _fact_exists(facts, insight):
            facts.append(
                {
                    "id": f"fact_{uuid.uuid4().hex[:12]}",
                    "fact": insight,
                    "source": "conversation",
                    "extractedAt": timestamp,
                }
            )

    node["notes"] = notes[-_runtime.max_notes_per_node :]
    node["facts"] = facts[-_runtime.max_facts_per_node :]
    node_path.write_text(json.dumps(node, indent=2), encoding="utf-8")

    # Keep session.json inline memoryNodes mirror in sync when present.
    session_path = session_dir / "session.json"
    if session_path.exists():
        session = _load_json_dict(session_path)
        memory_nodes = session.get("memoryNodes")
        if isinstance(memory_nodes, list):
            for idx, raw in enumerate(memory_nodes):
                if isinstance(raw, dict) and raw.get("id") == head_node_id:
                    memory_nodes[idx] = node
                    break
            session["memoryNodes"] = memory_nodes
            session_path.write_text(json.dumps(session, indent=2), encoding="utf-8")


def _fact_exists(facts: list, text: str) -> bool:
    for raw in facts:
        if isinstance(raw, dict) and raw.get("fact") == text:
            return True
    return False


def _load_json_list(path: Path) -> list:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, list):
        return raw
    return []


def _load_json_dict(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        return raw
    return {}


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item.strip())
    return result
