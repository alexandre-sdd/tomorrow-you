from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]


class ContextResolutionError(ValueError):
    """Raised when session/branch data cannot be resolved."""


@dataclass(frozen=True)
class ResolvedConversationContext:
    """Read-only context payload used by prompt composition and inference."""

    session_id: str
    branch_name: str
    user_profile: JsonDict
    self_card: JsonDict
    memory_facts: list[JsonDict]
    memory_notes: list[str]
    memory_path_node_ids: list[str]
    profile_summary: str


class ContextResolver:
    """Loads session and branch context from storage without writing anything."""

    def __init__(self, storage_root: str | Path = "storage/sessions") -> None:
        self.storage_root = Path(storage_root)

    def resolve(self, session_id: str, branch_name: str) -> ResolvedConversationContext:
        session_dir = self.storage_root / session_id
        session = self._load_required_json(session_dir / "session.json")

        branches = self._load_branches(session_dir, session)
        nodes_by_id = self._load_nodes(session_dir, session)

        head_node_id = self._find_head_node_id(branch_name, branches)
        path_nodes = self._walk_root_to_head(head_node_id, nodes_by_id)

        user_profile = session.get("userProfile")
        if not isinstance(user_profile, dict):
            raise ContextResolutionError("session.userProfile is missing or invalid")

        self_card = self._pick_branch_self_card(path_nodes, session)
        facts = self._collect_facts(path_nodes)
        notes = self._collect_notes(path_nodes)

        return ResolvedConversationContext(
            session_id=session_id,
            branch_name=branch_name,
            user_profile=user_profile,
            self_card=self_card,
            memory_facts=facts,
            memory_notes=notes,
            memory_path_node_ids=[str(node["id"]) for node in path_nodes],
            profile_summary=self._build_profile_summary(user_profile),
        )

    def find_branch_for_self(self, session_id: str, self_id: str) -> str:
        """
        Return the branch name whose headNodeId points to the memory node
        holding the given self_id as its selfCard.id.

        Raises ContextResolutionError if no matching node or branch is found.
        """
        session_dir = self.storage_root / session_id
        session = self._load_required_json(session_dir / "session.json")
        nodes_by_id = self._load_nodes(session_dir, session)
        branches = self._load_branches(session_dir, session)

        target_node_id: str | None = None
        for node_id, node in nodes_by_id.items():
            self_card = node.get("selfCard")
            if isinstance(self_card, dict) and self_card.get("id") == self_id:
                target_node_id = node_id
                break

        if target_node_id is None:
            raise ContextResolutionError(
                f"No memory node found with selfCard.id == '{self_id}' in session '{session_id}'"
            )

        for branch in branches:
            if branch.get("headNodeId") == target_node_id:
                name = branch.get("name")
                if isinstance(name, str) and name:
                    return name
                raise ContextResolutionError(
                    f"Branch pointing to node '{target_node_id}' has no valid name"
                )

        raise ContextResolutionError(
            f"No branch found with headNodeId == '{target_node_id}' (self_id='{self_id}')"
        )

    def _load_branches(self, session_dir: Path, session: JsonDict) -> list[JsonDict]:
        branches_path = session_dir / "memory" / "branches.json"
        if branches_path.exists():
            data = self._load_required_json(branches_path)
            if isinstance(data, list):
                return [row for row in data if isinstance(row, dict)]
            raise ContextResolutionError(f"Expected list in {branches_path}")

        raw = session.get("memoryBranches")
        if isinstance(raw, list):
            return [row for row in raw if isinstance(row, dict)]

        raise ContextResolutionError("No branch data found in memory/branches.json or session.memoryBranches")

    def _load_nodes(self, session_dir: Path, session: JsonDict) -> dict[str, JsonDict]:
        nodes_dir = session_dir / "memory" / "nodes"
        nodes_by_id: dict[str, JsonDict] = {}

        if nodes_dir.exists():
            for path in sorted(nodes_dir.glob("*.json")):
                node = self._load_required_json(path)
                node_id = node.get("id")
                if isinstance(node_id, str):
                    nodes_by_id[node_id] = node

        if nodes_by_id:
            return nodes_by_id

        raw_nodes = session.get("memoryNodes")
        if isinstance(raw_nodes, list):
            for node in raw_nodes:
                if isinstance(node, dict) and isinstance(node.get("id"), str):
                    nodes_by_id[node["id"]] = node

        if nodes_by_id:
            return nodes_by_id

        raise ContextResolutionError("No memory nodes found in memory/nodes or session.memoryNodes")

    def _find_head_node_id(self, branch_name: str, branches: list[JsonDict]) -> str:
        for branch in branches:
            if branch.get("name") == branch_name:
                head = branch.get("headNodeId")
                if isinstance(head, str) and head:
                    return head
                raise ContextResolutionError(f"Branch '{branch_name}' has no valid headNodeId")
        raise ContextResolutionError(f"Branch '{branch_name}' not found")

    def _walk_root_to_head(self, head_node_id: str, nodes_by_id: dict[str, JsonDict]) -> list[JsonDict]:
        chain: list[JsonDict] = []
        seen: set[str] = set()
        node_id = head_node_id

        while node_id:
            if node_id in seen:
                raise ContextResolutionError(f"Cycle detected while walking memory nodes at '{node_id}'")
            seen.add(node_id)

            node = nodes_by_id.get(node_id)
            if not node:
                raise ContextResolutionError(f"Memory node '{node_id}' not found")

            chain.append(node)
            parent_id = node.get("parentId")
            if parent_id is None:
                break
            if not isinstance(parent_id, str):
                raise ContextResolutionError(f"Memory node '{node_id}' has invalid parentId")
            node_id = parent_id

        chain.reverse()
        return chain

    def _pick_branch_self_card(self, path_nodes: list[JsonDict], session: JsonDict) -> JsonDict:
        for node in reversed(path_nodes):
            candidate = node.get("selfCard")
            if isinstance(candidate, dict):
                return candidate

        selected = session.get("selectedFutureSelf")
        if isinstance(selected, dict):
            return selected

        raise ContextResolutionError("No selfCard found for selected branch")

    def _collect_facts(self, path_nodes: list[JsonDict]) -> list[JsonDict]:
        facts: list[JsonDict] = []
        for node in path_nodes:
            node_facts = node.get("facts")
            if isinstance(node_facts, list):
                facts.extend(item for item in node_facts if isinstance(item, dict))
        return facts

    def _collect_notes(self, path_nodes: list[JsonDict]) -> list[str]:
        notes: list[str] = []
        for node in path_nodes:
            node_notes = node.get("notes")
            if isinstance(node_notes, list):
                notes.extend(item for item in node_notes if isinstance(item, str) and item.strip())
        return notes

    def _build_profile_summary(self, profile: JsonDict) -> str:
        core_values = self._join_str_list(profile.get("coreValues"), 4)
        fears = self._join_str_list(profile.get("fears"), 4)
        tensions = self._join_str_list(profile.get("hiddenTensions"), 3)
        decision_style = self._coerce_str(profile.get("decisionStyle"))
        dilemma = self._coerce_str(profile.get("currentDilemma"))

        lines = [
            f"Core values: {core_values}",
            f"Primary fears: {fears}",
            f"Hidden tensions: {tensions}",
            f"Decision style: {decision_style}",
            f"Current dilemma: {dilemma}",
        ]
        return "\n".join(lines)

    def _join_str_list(self, value: Any, limit: int) -> str:
        if not isinstance(value, list):
            return "none"
        cleaned = [v.strip() for v in value if isinstance(v, str) and v.strip()]
        if not cleaned:
            return "none"
        return "; ".join(cleaned[:limit])

    def _coerce_str(self, value: Any) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return "none"

    def _load_required_json(self, path: Path) -> Any:
        if not path.exists():
            raise ContextResolutionError(f"Missing file: {path}")
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) and not isinstance(data, list):
            raise ContextResolutionError(f"Invalid JSON object in {path}")
        return data
