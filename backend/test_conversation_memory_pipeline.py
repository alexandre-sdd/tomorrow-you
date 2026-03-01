from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.cli import backfill_transcript_insights as backfill_cli
from backend.engines import conversation_memory as cm
from backend.engines.future_gen_context import resolve_ancestor_context


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class ConversationMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_input_roles = list(cm._extract_cfg.input_roles)

    def tearDown(self) -> None:
        cm._extract_cfg.input_roles = self._original_input_roles

    def test_select_branch_conversation_entries_includes_assistant_when_configured(self) -> None:
        cm._extract_cfg.input_roles = ["user", "assistant"]
        transcript = [
            {
                "phase": "conversation",
                "role": "user",
                "branchName": "b1",
                "selfId": "s1",
                "content": "user line",
            },
            {
                "phase": "conversation",
                "role": "assistant",
                "branchName": "b1",
                "selfId": "s1",
                "content": "assistant line",
            },
            {
                "phase": "conversation",
                "role": "memory",
                "branchName": "b1",
                "selfId": "s1",
                "content": "memory line",
            },
            {
                "phase": "conversation",
                "role": "system",
                "branchName": "b1",
                "selfId": "s1",
                "content": "system line",
            },
        ]
        selected = cm._select_branch_conversation_entries(
            transcript=transcript,
            branch_name="b1",
            self_id="s1",
        )
        self.assertEqual([item["role"] for item in selected], ["user", "assistant"])
        self.assertEqual([item["content"] for item in selected], ["user line", "assistant line"])

    def test_recompute_and_replace_transcript_analysis_memory(self) -> None:
        cm._extract_cfg.input_roles = ["user", "assistant"]
        with tempfile.TemporaryDirectory() as tmp:
            storage_root = Path(tmp)
            session_id = "s_recompute"
            session_dir = storage_root / session_id
            branch_name = "branch_a"
            self_id = "self_a"
            self_name = "Self A"
            node_id = "node_a"

            _write_json(
                session_dir / "memory" / "branches.json",
                [
                    {"name": "root", "headNodeId": "node_root", "parentBranchName": None},
                    {"name": branch_name, "headNodeId": node_id, "parentBranchName": "root"},
                ],
            )
            _write_json(
                session_dir / "memory" / "nodes" / f"{node_id}.json",
                {
                    "id": node_id,
                    "parentId": "node_root",
                    "branchLabel": branch_name,
                    "facts": [
                        {"id": "f_keep", "fact": "seed", "source": "interview"},
                        {"id": "f_old", "fact": "old insight", "source": "transcript_analysis"},
                    ],
                    "notes": [
                        "Keep me",
                        "Transcript insight [old]: stale note",
                    ],
                    "selfCard": {"id": self_id, "name": self_name, "type": "future"},
                },
            )
            _write_json(
                session_dir / "session.json",
                {"id": session_id, "memoryNodes": []},
            )
            _write_json(
                session_dir / "transcript.json",
                [
                    {
                        "id": "te1",
                        "turn": 1,
                        "phase": "conversation",
                        "role": "user",
                        "selfId": self_id,
                        "selfName": self_name,
                        "branchName": branch_name,
                        "content": "Can Bali be a trial run?",
                        "timestamp": 1.0,
                    },
                    {
                        "id": "te2",
                        "turn": 2,
                        "phase": "conversation",
                        "role": "assistant",
                        "selfId": self_id,
                        "selfName": self_name,
                        "branchName": branch_name,
                        "content": "Bali first, then decide on Singapore.",
                        "timestamp": 1.1,
                    },
                    {
                        "id": "te_old_memory",
                        "turn": 3,
                        "phase": "conversation",
                        "role": "memory",
                        "selfId": self_id,
                        "selfName": self_name,
                        "branchName": branch_name,
                        "content": "Transcript insight [old]: stale note",
                        "timestamp": 1.2,
                    },
                ],
            )

            raw_first = json.dumps(
                {
                    "insights": [
                        {
                            "type": "experiment_path",
                            "element": "Bali is treated as a reversible experiment before bigger relocation choices.",
                            "evidence": "Bali first, then decide on Singapore.",
                            "why_it_matters": "Next branches should preserve experiment-first framing.",
                        }
                    ]
                }
            )
            with patch(
                "backend.engines.conversation_memory._extract_insights_with_llm",
                return_value=raw_first,
            ):
                first_added = cm.analyze_and_persist_transcript_insights(
                    session_id=session_id,
                    storage_root=storage_root,
                    branch_name=branch_name,
                    self_id=self_id,
                    self_name=self_name,
                    api_key="test-key",
                )
            self.assertEqual(len(first_added), 1)

            node_after_first = json.loads(
                (session_dir / "memory" / "nodes" / f"{node_id}.json").read_text(encoding="utf-8")
            )
            facts_after_first = node_after_first["facts"]
            self.assertEqual(
                len([f for f in facts_after_first if f.get("source") == "transcript_analysis"]),
                1,
            )
            self.assertTrue(any("Bali" in f.get("fact", "") for f in facts_after_first))
            self.assertFalse(any("stale note" in n for n in node_after_first["notes"]))

            with patch(
                "backend.engines.conversation_memory._extract_insights_with_llm",
                return_value='{"insights":[]}',
            ):
                second_added = cm.analyze_and_persist_transcript_insights(
                    session_id=session_id,
                    storage_root=storage_root,
                    branch_name=branch_name,
                    self_id=self_id,
                    self_name=self_name,
                    api_key="test-key",
                )
            self.assertEqual(second_added, [])

            node_after_second = json.loads(
                (session_dir / "memory" / "nodes" / f"{node_id}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                len([f for f in node_after_second["facts"] if f.get("source") == "transcript_analysis"]),
                0,
            )
            self.assertFalse(
                any(isinstance(n, str) and n.startswith("Transcript insight [") for n in node_after_second["notes"])
            )
            self.assertTrue(any(f.get("id") == "f_keep" for f in node_after_second["facts"]))

            transcript_after_second = json.loads(
                (session_dir / "transcript.json").read_text(encoding="utf-8")
            )
            self.assertFalse(
                any(
                    entry.get("role") == "memory"
                    and entry.get("branchName") == branch_name
                    and str(entry.get("content", "")).startswith("Transcript insight [")
                    for entry in transcript_after_second
                )
            )

    def test_analysis_persists_assistant_origin_detail(self) -> None:
        cm._extract_cfg.input_roles = ["user", "assistant"]
        with tempfile.TemporaryDirectory() as tmp:
            storage_root = Path(tmp)
            session_id = "s_bali"
            session_dir = storage_root / session_id
            branch_name = "branch_bali"
            self_id = "self_bali"
            self_name = "Self Bali"
            node_id = "node_bali"

            _write_json(
                session_dir / "memory" / "branches.json",
                [
                    {"name": "root", "headNodeId": "node_root", "parentBranchName": None},
                    {"name": branch_name, "headNodeId": node_id, "parentBranchName": "root"},
                ],
            )
            _write_json(
                session_dir / "memory" / "nodes" / f"{node_id}.json",
                {
                    "id": node_id,
                    "parentId": "node_root",
                    "branchLabel": branch_name,
                    "facts": [],
                    "notes": [],
                    "selfCard": {"id": self_id, "name": self_name, "type": "future"},
                },
            )
            _write_json(session_dir / "session.json", {"id": session_id, "memoryNodes": []})
            _write_json(
                session_dir / "transcript.json",
                [
                    {
                        "id": "te1",
                        "turn": 1,
                        "phase": "conversation",
                        "role": "assistant",
                        "selfId": self_id,
                        "selfName": self_name,
                        "branchName": branch_name,
                        "content": "We moved to Bali first to test remote life.",
                        "timestamp": 1.0,
                    },
                    {
                        "id": "te2",
                        "turn": 2,
                        "phase": "conversation",
                        "role": "user",
                        "selfId": self_id,
                        "selfName": self_name,
                        "branchName": branch_name,
                        "content": "That Bali trial changed how I think about risk.",
                        "timestamp": 1.1,
                    },
                ],
            )

            with patch(
                "backend.engines.conversation_memory._extract_insights_with_llm",
                return_value=json.dumps(
                    {
                        "insights": [
                            {
                                "type": "location_trial",
                                "element": "Bali was a formative trial period before committing to a larger move.",
                                "evidence": "We moved to Bali first to test remote life.",
                                "why_it_matters": "Branching should preserve Bali as a meaningful decision node.",
                            }
                        ]
                    }
                ),
            ):
                cm.analyze_and_persist_transcript_insights(
                    session_id=session_id,
                    storage_root=storage_root,
                    branch_name=branch_name,
                    self_id=self_id,
                    self_name=self_name,
                    api_key="test-key",
                )

            node_after = json.loads(
                (session_dir / "memory" / "nodes" / f"{node_id}.json").read_text(encoding="utf-8")
            )
            self.assertTrue(
                any("Bali" in f.get("fact", "") for f in node_after.get("facts", [])),
                "Expected Bali detail to be present in transcript_analysis facts",
            )


class FutureGenContextTests(unittest.TestCase):
    def test_resolve_ancestor_context_includes_assistant_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage_root = Path(tmp)
            session_id = "s_ctx_assistant"
            session_dir = storage_root / session_id
            parent_self_id = "self_parent"
            parent_self_name = "Self Parent"

            _write_json(
                session_dir / "memory" / "nodes" / "node_root.json",
                {
                    "id": "node_root",
                    "parentId": None,
                    "branchLabel": "root",
                    "selfCard": None,
                },
            )
            _write_json(
                session_dir / "memory" / "nodes" / "node_parent.json",
                {
                    "id": "node_parent",
                    "parentId": "node_root",
                    "branchLabel": "b_parent",
                    "selfCard": {"id": parent_self_id, "name": parent_self_name},
                },
            )
            _write_json(
                session_dir / "transcript.json",
                [
                    {
                        "phase": "conversation",
                        "role": "assistant",
                        "selfName": parent_self_name,
                        "content": "Bali gave us a low-risk experiment.",
                    },
                    {
                        "phase": "conversation",
                        "role": "user",
                        "selfName": parent_self_name,
                        "content": "I liked the Bali trial.",
                    },
                ],
            )

            _, excerpts = resolve_ancestor_context(
                session_id=session_id,
                parent_self_id=parent_self_id,
                storage_path=str(storage_root),
                include_roles=["assistant"],
            )

            self.assertEqual(len(excerpts), 1)
            self.assertIn("assistant", excerpts[0].lower())
            self.assertIn("Bali", excerpts[0])

    def test_resolve_ancestor_context_all_turns_keeps_assistant_storyline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage_root = Path(tmp)
            session_id = "s_ctx_all"
            session_dir = storage_root / session_id
            parent_self_id = "self_story"
            parent_self_name = "Self Story"

            _write_json(
                session_dir / "memory" / "nodes" / "node_root.json",
                {
                    "id": "node_root",
                    "parentId": None,
                    "branchLabel": "root",
                    "selfCard": None,
                },
            )
            _write_json(
                session_dir / "memory" / "nodes" / "node_story.json",
                {
                    "id": "node_story",
                    "parentId": "node_root",
                    "branchLabel": "b_story",
                    "selfCard": {"id": parent_self_id, "name": parent_self_name},
                },
            )
            _write_json(
                session_dir / "transcript.json",
                [
                    {
                        "phase": "conversation",
                        "role": "assistant",
                        "selfName": parent_self_name,
                        "content": "We tested Bali before deciding anything permanent.",
                    },
                    {
                        "phase": "conversation",
                        "role": "memory",
                        "selfName": parent_self_name,
                        "content": "Transcript insight [location_trial]: Bali mattered.",
                    },
                    {
                        "phase": "conversation",
                        "role": "user",
                        "selfName": parent_self_name,
                        "content": "That Bali test reduced fear.",
                    },
                ],
            )

            _, excerpts = resolve_ancestor_context(
                session_id=session_id,
                parent_self_id=parent_self_id,
                storage_path=str(storage_root),
                include_roles=["user", "assistant", "memory"],
            )

            joined = "\n".join(excerpts)
            self.assertIn("Bali", joined)
            self.assertIn("assistant", joined.lower())


class BackfillCliTests(unittest.TestCase):
    def test_backfill_cli_updates_target_branches_and_reports_totals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            storage_root = Path(tmp)
            session_id = "s_backfill"
            session_dir = storage_root / session_id
            _write_json(
                session_dir / "memory" / "branches.json",
                [
                    {"name": "root", "headNodeId": "node_root", "parentBranchName": None},
                    {"name": "branch_one", "headNodeId": "node_one", "parentBranchName": "root"},
                    {"name": "branch_two", "headNodeId": "node_two", "parentBranchName": "root"},
                ],
            )
            _write_json(
                session_dir / "memory" / "nodes" / "node_one.json",
                {"id": "node_one", "selfCard": {"id": "self_1", "name": "Self One"}},
            )
            _write_json(
                session_dir / "memory" / "nodes" / "node_two.json",
                {"id": "node_two", "selfCard": {"id": "self_2", "name": "Self Two"}},
            )

            args = backfill_cli.build_parser().parse_args(
                ["--session-id", session_id, "--storage-root", str(storage_root)]
            )
            fake_settings = SimpleNamespace(mistral_api_key="test-key")

            with patch.object(backfill_cli, "get_settings", return_value=fake_settings), patch.object(
                backfill_cli,
                "analyze_and_persist_transcript_insights",
                side_effect=[[{"id": 1}], [{"id": 2}, {"id": 3}]],
            ) as analyze_mock:
                out = io.StringIO()
                with redirect_stdout(out):
                    rc = backfill_cli.run(args)

            output = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertEqual(analyze_mock.call_count, 2)
            self.assertIn("branch_one", output)
            self.assertIn("branch_two", output)
            self.assertIn("processed: 2", output)
            self.assertIn("total insights written: 3", output)


if __name__ == "__main__":
    unittest.main()
