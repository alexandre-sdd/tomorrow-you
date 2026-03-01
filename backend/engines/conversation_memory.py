from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from backend.config.runtime import get_runtime_config

from .mistral_client import MistralChatClient, MistralChatConfig

_runtime = get_runtime_config()
_memory_cfg = _runtime.conversation_memory
_extract_cfg = _runtime.memory_extraction


def append_conversation_turn(
    *,
    session_id: str,
    storage_root: str | Path,
    branch_name: str,
    self_id: str | None,
    self_name: str | None,
    user_text: str,
    assistant_text: str,
) -> None:
    """
    Persist one conversation turn (user + assistant) to transcript.json.
    """
    if not _memory_cfg.enabled:
        return

    cleaned_user = user_text.strip()
    cleaned_assistant = assistant_text.strip()
    if not cleaned_user or not cleaned_assistant:
        return

    session_dir = Path(storage_root) / session_id
    transcript_path = session_dir / "transcript.json"
    transcript = _load_json_list(transcript_path)

    # Idempotency guard: skip duplicate final pair.
    if len(transcript) >= 2:
        last_user = transcript[-2]
        last_assistant = transcript[-1]
        if (
            isinstance(last_user, dict)
            and isinstance(last_assistant, dict)
            and last_user.get("phase") == "conversation"
            and last_assistant.get("phase") == "conversation"
            and last_user.get("role") == "user"
            and last_assistant.get("role") == "assistant"
            and last_user.get("content") == cleaned_user
            and last_assistant.get("content") == cleaned_assistant
            and last_user.get("selfId") == self_id
            and last_assistant.get("selfId") == self_id
            and last_user.get("branchName") == branch_name
            and last_assistant.get("branchName") == branch_name
        ):
            return

    now = time.time()
    entries = [
        _new_transcript_entry(
            role="user",
            content=cleaned_user,
            branch_name=branch_name,
            self_id=self_id,
            self_name=self_name,
            timestamp=now,
        ),
        _new_transcript_entry(
            role="assistant",
            content=cleaned_assistant,
            branch_name=branch_name,
            self_id=self_id,
            self_name=self_name,
            timestamp=now,
        ),
    ]
    _append_transcript_entries(transcript, entries)
    _trim_transcript(transcript)
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")


def analyze_and_persist_transcript_insights(
    *,
    session_id: str,
    storage_root: str | Path,
    branch_name: str,
    self_id: str | None,
    self_name: str | None,
    api_key: str,
) -> list[dict[str, str]]:
    """
    Analyze branch transcript with LLM and persist extracted insights to:
    - transcript.json (role=memory)
    - current branch memory node (facts + notes)
    """
    if not _memory_cfg.enabled or not _extract_cfg.enabled:
        return []

    if not api_key.strip():
        return []

    session_dir = Path(storage_root) / session_id
    transcript_path = session_dir / "transcript.json"
    transcript = _load_json_list(transcript_path)
    if not transcript:
        return []

    convo_entries = _select_branch_conversation_entries(
        transcript=transcript,
        branch_name=branch_name,
        self_id=self_id,
    )
    if len(convo_entries) < 2:
        return []
    if not _has_unanalyzed_conversation(
        transcript=transcript,
        branch_name=branch_name,
        self_id=self_id,
    ):
        return []

    clipped_entries = convo_entries[-_extract_cfg.max_messages_for_analysis :]
    raw_output = _extract_insights_with_llm(clipped_entries, api_key=api_key)
    insights = _parse_insights(raw_output)
    if not insights:
        return []

    now = time.time()
    return _persist_insights(
        session_dir=session_dir,
        branch_name=branch_name,
        self_id=self_id,
        self_name=self_name,
        insights=insights,
        timestamp=now,
    )


def _select_branch_conversation_entries(
    *,
    transcript: list,
    branch_name: str,
    self_id: str | None,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for raw in transcript:
        if not isinstance(raw, dict):
            continue
        if raw.get("phase") != "conversation":
            continue
        role = raw.get("role")
        if role not in {"user", "assistant"}:
            continue

        entry_branch = raw.get("branchName")
        entry_self = raw.get("selfId")
        if branch_name and entry_branch and entry_branch != branch_name:
            continue
        if self_id and entry_self and entry_self != self_id:
            continue

        content = raw.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        selected.append({"role": str(role), "content": content.strip()})
    return selected


def _has_unanalyzed_conversation(
    *,
    transcript: list,
    branch_name: str,
    self_id: str | None,
) -> bool:
    latest_conversation_turn = 0
    latest_memory_turn = 0

    for raw in transcript:
        if not isinstance(raw, dict):
            continue
        if raw.get("phase") != "conversation":
            continue
        entry_branch = raw.get("branchName")
        entry_self = raw.get("selfId")
        if branch_name and entry_branch and entry_branch != branch_name:
            continue
        if self_id and entry_self and entry_self != self_id:
            continue

        turn = raw.get("turn")
        turn_num = int(turn) if isinstance(turn, int) or (isinstance(turn, str) and turn.isdigit()) else 0
        role = raw.get("role")
        if role in {"user", "assistant"} and turn_num > latest_conversation_turn:
            latest_conversation_turn = turn_num
        if role == "memory":
            content = raw.get("content")
            if isinstance(content, str) and content.startswith("Transcript insight ["):
                if turn_num > latest_memory_turn:
                    latest_memory_turn = turn_num

    return latest_conversation_turn > latest_memory_turn


def _extract_insights_with_llm(entries: list[dict[str, str]], *, api_key: str) -> str:
    chat_cfg = MistralChatConfig(
        model=_extract_cfg.model,
        temperature=_extract_cfg.temperature,
        top_p=_extract_cfg.top_p,
        max_tokens=_extract_cfg.max_tokens,
        timeout_seconds=_extract_cfg.timeout_seconds,
    )
    client = MistralChatClient(api_key=api_key, config=chat_cfg)
    transcript_block = "\n".join(
        f"{idx + 1}. [{item['role'].upper()}] {item['content']}"
        for idx, item in enumerate(entries)
    )

    system_prompt = (
        "You extract branching-relevant signals from a conversation transcript.\n"
        "Return ONLY JSON with this shape:\n"
        '{"insights":[{"type":"string","element":"string","evidence":"string","why_it_matters":"string"}]}\n'
        "Rules:\n"
        "- No fixed categories. Invent the most useful type labels for this transcript.\n"
        "- Extract as many or as few insights as justified by evidence.\n"
        "- Focus on durable signals: values, fears, constraints, hopes, priorities, trade-offs, identity statements.\n"
        "- Avoid duplicates and generic advice.\n"
        "- Every insight must be grounded in transcript evidence.\n\n"
        "Few-shot example transcript:\n"
        "1. [USER] I want the promotion, but I am scared the move will distance me from my wife.\n"
        "2. [ASSISTANT] What matters most if those goals conflict?\n"
        "3. [USER] Long term I want both, but I prioritize the marriage if I must choose.\n\n"
        "Few-shot example output:\n"
        '{"insights":[{"type":"relationship_priority","element":"He will prioritize marital closeness over career acceleration when forced to choose.","evidence":"\\"I prioritize the marriage if I must choose.\\"","why_it_matters":"Future branches should account for a strong relational decision constraint."},{"type":"ambition_with_anxiety","element":"He still seeks career growth but associates relocation with emotional risk.","evidence":"\\"I want the promotion, but I am scared...\\"","why_it_matters":"Future scenarios should preserve ambition while modeling emotional cost and mitigation."}]}\n'
    )
    user_prompt = (
        "Analyze this transcript and extract key elements for future branching:\n\n"
        f"{transcript_block}"
    )
    return client.chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )


def _parse_insights(raw_output: str) -> list[dict[str, str]]:
    payload = _extract_json_payload(raw_output)
    if not isinstance(payload, dict):
        return []

    raw_items = payload.get("insights")
    if not isinstance(raw_items, list):
        # fallback for alternative key names
        raw_items = payload.get("elements")
    if not isinstance(raw_items, list):
        return []

    insights: list[dict[str, str]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        type_value = _clean_text(raw.get("type") or raw.get("kind") or raw.get("category") or "signal")
        element_value = _clean_text(
            raw.get("element") or raw.get("insight") or raw.get("fact") or raw.get("summary")
        )
        evidence_value = _clean_text(raw.get("evidence") or raw.get("quote") or "")
        why_value = _clean_text(raw.get("why_it_matters") or raw.get("rationale") or raw.get("importance") or "")

        if not element_value:
            continue
        insights.append(
            {
                "type": type_value or "signal",
                "element": element_value,
                "evidence": evidence_value,
                "why_it_matters": why_value,
            }
        )

    return _dedupe_insights(insights)


def _persist_insights(
    *,
    session_dir: Path,
    branch_name: str,
    self_id: str | None,
    self_name: str | None,
    insights: list[dict[str, str]],
    timestamp: float,
) -> list[dict[str, str]]:
    head_node_id = _resolve_branch_head_node_id(session_dir=session_dir, branch_name=branch_name)
    if not head_node_id:
        return []

    node_path = session_dir / "memory" / "nodes" / f"{head_node_id}.json"
    node = _load_json_dict(node_path)
    if not node:
        return []

    notes = list(node.get("notes") or [])
    facts = list(node.get("facts") or [])
    existing_keys = _existing_insight_keys(facts=facts)

    added: list[dict[str, str]] = []
    memory_entries: list[dict[str, Any]] = []
    for insight in insights:
        key = _insight_key(insight["type"], insight["element"])
        if key in existing_keys:
            continue
        existing_keys.add(key)
        added.append(insight)

        fact_entry: dict[str, Any] = {
            "id": f"fact_{uuid.uuid4().hex[:12]}",
            "fact": insight["element"],
            "type": insight["type"],
            "source": "transcript_analysis",
            "extractedAt": timestamp,
        }
        if insight.get("evidence"):
            fact_entry["evidence"] = insight["evidence"]
        if insight.get("why_it_matters"):
            fact_entry["whyItMatters"] = insight["why_it_matters"]
        facts.append(fact_entry)

        note = f"Transcript insight [{insight['type']}]: {insight['element']}"
        if note not in notes:
            notes.append(note)

        memory_entries.append(
            _new_transcript_entry(
                role="memory",
                content=note,
                branch_name=branch_name,
                self_id=self_id,
                self_name=self_name,
                timestamp=timestamp,
            )
        )

    if not added:
        return []

    node["notes"] = notes[-_memory_cfg.max_notes_per_node :]
    node["facts"] = facts[-_memory_cfg.max_facts_per_node :]
    node_path.parent.mkdir(parents=True, exist_ok=True)
    node_path.write_text(json.dumps(node, indent=2), encoding="utf-8")
    _sync_session_memory_nodes(session_dir=session_dir, node=node)

    transcript_path = session_dir / "transcript.json"
    transcript = _load_json_list(transcript_path)
    for entry in memory_entries:
        if _memory_entry_exists(
            transcript=transcript,
            branch_name=branch_name,
            self_id=self_id,
            content=str(entry.get("content", "")),
        ):
            continue
        _append_transcript_entries(transcript, [entry])
    _trim_transcript(transcript)
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")

    return added


def _memory_entry_exists(
    *,
    transcript: list,
    branch_name: str,
    self_id: str | None,
    content: str,
) -> bool:
    for raw in transcript:
        if not isinstance(raw, dict):
            continue
        if raw.get("phase") != "conversation":
            continue
        if raw.get("role") != "memory":
            continue
        if raw.get("content") != content:
            continue
        if raw.get("branchName") != branch_name:
            continue
        if self_id and raw.get("selfId") and raw.get("selfId") != self_id:
            continue
        return True
    return False


def _resolve_branch_head_node_id(*, session_dir: Path, branch_name: str) -> str | None:
    branches_path = session_dir / "memory" / "branches.json"
    for raw in _load_json_list(branches_path):
        if not isinstance(raw, dict):
            continue
        if raw.get("name") != branch_name:
            continue
        head = raw.get("headNodeId")
        if isinstance(head, str) and head:
            return head
    return None


def _sync_session_memory_nodes(*, session_dir: Path, node: dict) -> None:
    session_path = session_dir / "session.json"
    session = _load_json_dict(session_path)
    if not session:
        return
    memory_nodes = session.get("memoryNodes")
    if not isinstance(memory_nodes, list):
        return

    node_id = node.get("id")
    if not isinstance(node_id, str) or not node_id:
        return

    replaced = False
    for idx, raw in enumerate(memory_nodes):
        if isinstance(raw, dict) and raw.get("id") == node_id:
            memory_nodes[idx] = node
            replaced = True
            break
    if not replaced:
        memory_nodes.append(node)
    session["memoryNodes"] = memory_nodes
    session_path.write_text(json.dumps(session, indent=2), encoding="utf-8")


def _existing_insight_keys(*, facts: list) -> set[str]:
    keys: set[str] = set()
    for raw in facts:
        if not isinstance(raw, dict):
            continue
        if raw.get("source") != "transcript_analysis":
            continue
        type_value = _clean_text(raw.get("type") or "signal")
        fact_value = _clean_text(raw.get("fact") or "")
        if not fact_value:
            continue
        keys.add(_insight_key(type_value or "signal", fact_value))
    return keys


def _insight_key(type_value: str, element_value: str) -> str:
    return f"{type_value.strip().lower()}::{element_value.strip().lower()}"


def _new_transcript_entry(
    *,
    role: str,
    content: str,
    branch_name: str,
    self_id: str | None,
    self_name: str | None,
    timestamp: float,
) -> dict[str, Any]:
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


def _append_transcript_entries(transcript: list, entries: list[dict[str, Any]]) -> None:
    start_turn = len(transcript) + 1
    for idx, entry in enumerate(entries):
        entry["turn"] = start_turn + idx
        transcript.append(entry)


def _trim_transcript(transcript: list) -> None:
    if len(transcript) <= _memory_cfg.max_transcript_entries:
        return
    overflow = len(transcript) - _memory_cfg.max_transcript_entries
    del transcript[:overflow]
    for idx, entry in enumerate(transcript, start=1):
        if isinstance(entry, dict):
            entry["turn"] = idx


def _extract_json_payload(raw_text: str) -> dict[str, Any] | None:
    stripped = raw_text.strip()
    if not stripped:
        return None

    direct = _try_parse_json(stripped)
    if isinstance(direct, dict):
        return direct

    if stripped.startswith("```"):
        fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, flags=re.S | re.I)
        if fence_match:
            parsed = _try_parse_json(fence_match.group(1))
            if isinstance(parsed, dict):
                return parsed

    brace_match = re.search(r"\{.*\}", stripped, flags=re.S)
    if brace_match:
        parsed = _try_parse_json(brace_match.group(0))
        if isinstance(parsed, dict):
            return parsed
    return None


def _try_parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip()


def _dedupe_insights(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for item in items:
        key = _insight_key(item.get("type", "signal"), item.get("element", ""))
        if key == "signal::" or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _load_json_list(path: Path) -> list:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, list):
        return raw
    return []


def _load_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        return raw
    return {}
