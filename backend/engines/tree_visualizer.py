"""
Tree Visualizer

Utilities for rendering and navigating the future self exploration tree.
Provides ASCII visualization, path finding, and statistics for CLI and testing.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

from backend.models.schemas import SelfCard


class TreeVisualizerError(Exception):
    """Base exception for tree visualization errors."""
    pass


class TreeVisualizer:
    """Visualizes and analyzes future self exploration tree."""

    def __init__(self, storage_root: str):
        self.storage_root = storage_root

    def _load_session(self, session_id: str) -> dict[str, Any]:
        """Load session data."""
        session_path = Path(self.storage_root) / session_id / "session.json"
        if not session_path.exists():
            raise TreeVisualizerError(f"Session {session_id} not found")
        return json.loads(session_path.read_text())

    def _load_transcript(self, session_id: str) -> list[dict[str, Any]]:
        """Load transcript data."""
        transcript_path = Path(self.storage_root) / session_id / "transcript.json"
        if not transcript_path.exists():
            return []
        return json.loads(transcript_path.read_text())

    def render_tree(
        self,
        session_id: str,
        current_self_id: str | None = None,
        show_stats: bool = True,
    ) -> str:
        """
        Render ASCII tree visualization of exploration structure.

        Args:
            session_id: Session identifier
            current_self_id: Optional ID of current self to highlight
            show_stats: Whether to include statistics

        Returns:
            Formatted ASCII tree string
        """
        session_data = self._load_session(session_id)
        current_self = session_data.get("currentSelf")
        future_selves_full = session_data.get("futureSelvesFull", {})
        exploration_paths = session_data.get("explorationPaths", {})

        if not current_self:
            return "No exploration tree yet. Complete onboarding first."

        lines = []
        lines.append("=" * 70)
        lines.append("EXPLORATION TREE")
        lines.append("=" * 70)
        lines.append("")

        # Root node (CurrentSelf)
        current_name = current_self.get("name", "Current Self")
        lines.append(f"🌱 {current_name} (Current)")
        lines.append("")

        # Build tree recursively
        if "root" in exploration_paths:
            root_children = exploration_paths["root"]
            for i, child_id in enumerate(root_children):
                is_last = i == len(root_children) - 1
                self._render_node(
                    lines=lines,
                    self_id=child_id,
                    future_selves_full=future_selves_full,
                    exploration_paths=exploration_paths,
                    current_self_id=current_self_id,
                    prefix="",
                    is_last=is_last,
                )

        if show_stats:
            lines.append("")
            stats = self.get_branch_statistics(session_id)
            lines.append("-" * 70)
            lines.append("STATISTICS")
            lines.append("-" * 70)
            lines.append(f"Total Future Selves: {stats['total_selves']}")
            lines.append(f"Maximum Depth: {stats['max_depth']}")
            lines.append(f"Branches with Conversations: {stats['branches_with_conversations']}")
            lines.append(f"Total Conversation Turns: {stats['total_conversation_turns']}")
            lines.append("")
            
            if stats['depth_distribution']:
                lines.append("Depth Distribution:")
                for depth, count in sorted(stats['depth_distribution'].items()):
                    lines.append(f"  Depth {depth}: {count} selves")

        lines.append("=" * 70)

        return "\n".join(lines)

    def _render_node(
        self,
        lines: list[str],
        self_id: str,
        future_selves_full: dict[str, Any],
        exploration_paths: dict[str, list[str]],
        current_self_id: str | None,
        prefix: str,
        is_last: bool,
    ) -> None:
        """Recursively render a node and its children."""
        if self_id not in future_selves_full:
            return

        self_data = future_selves_full[self_id]
        self_card = SelfCard(**self_data)

        # Determine connector
        connector = "└── " if is_last else "├── "
        
        # Highlight current self
        highlight = "→ " if self_id == current_self_id else "  "
        
        # Format node line
        node_line = f"{prefix}{connector}{highlight}{self_card.name}"
        
        # Add depth indicator
        node_line += f" (depth {self_card.depth_level})"
        
        # Add conversation indicator
        if self_card.children_ids:
            node_line += f" [+{len(self_card.children_ids)} children]"
        
        lines.append(node_line)

        # Render children
        children_ids = exploration_paths.get(self_id, [])
        if children_ids:
            # Prepare prefix for children
            extension = "    " if is_last else "│   "
            new_prefix = prefix + extension

            for i, child_id in enumerate(children_ids):
                child_is_last = i == len(children_ids) - 1
                self._render_node(
                    lines=lines,
                    self_id=child_id,
                    future_selves_full=future_selves_full,
                    exploration_paths=exploration_paths,
                    current_self_id=current_self_id,
                    prefix=new_prefix,
                    is_last=child_is_last,
                )

    def get_navigation_path(
        self,
        session_id: str,
        from_self_id: str,
        to_self_id: str,
    ) -> list[str]:
        """
        Find path between two selves in the tree.

        Args:
            session_id: Session identifier
            from_self_id: Starting self ID
            to_self_id: Target self ID

        Returns:
            List of self IDs representing path from start to target

        Raises:
            TreeVisualizerError: If no path exists
        """
        session_data = self._load_session(session_id)
        future_selves_full = session_data.get("futureSelvesFull", {})
        exploration_paths = session_data.get("explorationPaths", {})

        if from_self_id not in future_selves_full or to_self_id not in future_selves_full:
            raise TreeVisualizerError("One or both selves not found")

        # Build adjacency list (bidirectional)
        graph: dict[str, list[str]] = {}
        
        # Add root connections
        if "root" in exploration_paths:
            graph["root"] = exploration_paths["root"]
            for child_id in exploration_paths["root"]:
                graph.setdefault(child_id, []).append("root")

        # Add other connections
        for parent_id, children_ids in exploration_paths.items():
            if parent_id == "root":
                continue
            graph.setdefault(parent_id, [])
            for child_id in children_ids:
                graph[parent_id].append(child_id)
                graph.setdefault(child_id, []).append(parent_id)

        # BFS to find path
        queue: deque[tuple[str, list[str]]] = deque([(from_self_id, [from_self_id])])
        visited = {from_self_id}

        while queue:
            current, path = queue.popleft()

            if current == to_self_id:
                return path

            for neighbor in graph.get(current, []):
                if neighbor not in visited and neighbor != "root":
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        raise TreeVisualizerError(f"No path found from {from_self_id} to {to_self_id}")

    def get_branch_statistics(self, session_id: str) -> dict[str, Any]:
        """
        Get statistics about exploration tree.

        Returns dict with:
        - total_selves: Total number of generated future selves
        - max_depth: Maximum depth reached
        - branches_with_conversations: Number of selves with conversation history
        - total_conversation_turns: Total conversation turns across all branches
        - depth_distribution: Dict mapping depth level to count of selves
        - conversation_distribution: Dict mapping self_id to conversation turn count
        """
        session_data = self._load_session(session_id)
        future_selves_full = session_data.get("futureSelvesFull", {})
        transcript = self._load_transcript(session_id)

        # Count conversation turns per self
        conversation_counts: dict[str, int] = {}
        for entry in transcript:
            if entry.get("phase") == "conversation":
                self_id = entry.get("selfId")
                if self_id:
                    conversation_counts[self_id] = conversation_counts.get(self_id, 0) + 1

        # Analyze depth distribution
        depth_dist: dict[int, int] = {}
        max_depth = 0

        for self_data in future_selves_full.values():
            self_card = SelfCard(**self_data)
            depth = self_card.depth_level
            depth_dist[depth] = depth_dist.get(depth, 0) + 1
            max_depth = max(max_depth, depth)

        return {
            "total_selves": len(future_selves_full),
            "max_depth": max_depth,
            "branches_with_conversations": len(conversation_counts),
            "total_conversation_turns": sum(conversation_counts.values()),
            "depth_distribution": depth_dist,
            "conversation_distribution": conversation_counts,
        }

    def list_available_branches(
        self,
        session_id: str,
        with_conversations_only: bool = False,
    ) -> list[dict[str, Any]]:
        """
        List all available branches for navigation/conversation.

        Args:
            session_id: Session identifier
            with_conversations_only: If True, only return branches with conversation history

        Returns:
            List of dicts with self_id, name, depth_level, conversation_turns
        """
        session_data = self._load_session(session_id)
        future_selves_full = session_data.get("futureSelvesFull", {})
        transcript = self._load_transcript(session_id)

        # Count conversation turns
        conversation_counts: dict[str, int] = {}
        for entry in transcript:
            if entry.get("phase") == "conversation":
                self_id = entry.get("selfId")
                if self_id:
                    conversation_counts[self_id] = conversation_counts.get(self_id, 0) + 1

        branches = []
        for self_id, self_data in future_selves_full.items():
            self_card = SelfCard(**self_data)
            conv_turns = conversation_counts.get(self_id, 0)

            if with_conversations_only and conv_turns == 0:
                continue

            branches.append({
                "self_id": self_id,
                "name": self_card.name,
                "depth_level": self_card.depth_level,
                "conversation_turns": conv_turns,
                "has_children": len(self_card.children_ids) > 0,
                "num_children": len(self_card.children_ids),
            })

        # Sort by depth, then name
        branches.sort(key=lambda b: (b["depth_level"], b["name"]))

        return branches

    def get_ancestors(self, session_id: str, self_id: str) -> list[dict[str, Any]]:
        """
        Get all ancestors of a self, from root to parent.

        Args:
            session_id: Session identifier
            self_id: Self to get ancestors for

        Returns:
            List of ancestor dicts (self_id, name, depth_level) from root to parent
        """
        session_data = self._load_session(session_id)
        future_selves_full = session_data.get("futureSelvesFull", {})

        if self_id not in future_selves_full:
            raise TreeVisualizerError(f"Self {self_id} not found")

        ancestors = []
        current_id = self_id
        current_data = future_selves_full[current_id]
        current_card = SelfCard(**current_data)

        # Traverse up to root
        while current_card.parent_self_id:
            parent_id = current_card.parent_self_id
            if parent_id not in future_selves_full:
                break

            parent_data = future_selves_full[parent_id]
            parent_card = SelfCard(**parent_data)

            ancestors.append({
                "self_id": parent_id,
                "name": parent_card.name,
                "depth_level": parent_card.depth_level,
            })

            current_id = parent_id
            current_data = parent_data
            current_card = parent_card

        # Reverse to get root-to-parent order
        ancestors.reverse()

        return ancestors

    def get_siblings(self, session_id: str, self_id: str) -> list[dict[str, Any]]:
        """
        Get all siblings of a self (children of same parent).

        Args:
            session_id: Session identifier
            self_id: Self to get siblings for

        Returns:
            List of sibling dicts (self_id, name, depth_level), excluding self
        """
        session_data = self._load_session(session_id)
        future_selves_full = session_data.get("futureSelvesFull", {})
        exploration_paths = session_data.get("explorationPaths", {})

        if self_id not in future_selves_full:
            raise TreeVisualizerError(f"Self {self_id} not found")

        self_data = future_selves_full[self_id]
        self_card = SelfCard(**self_data)

        parent_id = self_card.parent_self_id or "root"
        sibling_ids = exploration_paths.get(parent_id, [])

        siblings = []
        for sibling_id in sibling_ids:
            if sibling_id == self_id:
                continue

            if sibling_id in future_selves_full:
                sibling_data = future_selves_full[sibling_id]
                sibling_card = SelfCard(**sibling_data)

                siblings.append({
                    "self_id": sibling_id,
                    "name": sibling_card.name,
                    "depth_level": sibling_card.depth_level,
                })

        return siblings
