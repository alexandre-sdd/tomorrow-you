from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, TypedDict

from backend.config.runtime import get_runtime_config

from .context_resolver import ResolvedConversationContext


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class PromptComposerConfig:
    _runtime = get_runtime_config().prompt_composer
    max_memory_facts: int = _runtime.max_memory_facts
    max_memory_notes: int = _runtime.max_memory_notes
    max_history_turns: int = _runtime.max_history_turns


class PromptComposer:
    """Builds model-ready prompts from resolved branch context."""

    def __init__(self, config: PromptComposerConfig | None = None) -> None:
        self.config = config or PromptComposerConfig()

    def compose_system_prompt(self, context: ResolvedConversationContext) -> str:
        self_card = context.self_card

        persona_name = self._safe_text(self_card.get("name"), "Future Self")
        optimization_goal = self._safe_text(self_card.get("optimizationGoal"), "none")
        tone_of_voice = self._safe_text(self_card.get("toneOfVoice"), "natural")
        worldview = self._safe_text(self_card.get("worldview"), "none")
        core_belief = self._safe_text(self_card.get("coreBelief"), "none")
        trade_off = self._safe_text(self_card.get("tradeOff"), "none")

        facts_block = self._format_memory_facts(context.memory_facts)
        notes_block = self._format_notes(context.memory_notes)

        return (
            f"You are {persona_name}, a possible future version of the user who chose the branch "
            f"'{context.branch_name}'.\n\n"
            "Identity constraints:\n"
            f"- Optimization goal: {optimization_goal}\n"
            f"- Tone of voice: {tone_of_voice}\n"
            f"- Worldview: {worldview}\n"
            f"- Core belief: {core_belief}\n"
            f"- Trade-off paid: {trade_off}\n\n"
            "User profile context:\n"
            f"{context.profile_summary}\n\n"
            "Memory facts from root to current branch:\n"
            f"{facts_block}\n\n"
            "Additional memory notes:\n"
            f"{notes_block}\n\n"
            "Conversation rules:\n"
            "1. Stay in character as this future self. Never mention being an AI, model, or prompt.\n"
            "2. Be natural and conversational. No robotic or generic coaching language.\n"
            "3. Be helpful and honest about trade-offs. Do not blindly agree with the user.\n"
            "4. Default response length: 4-8 sentences unless the user asks for deep detail.\n"
            "5. If context is ambiguous, ask one precise clarifying question.\n"
            "6. Keep continuity with prior turns in this chat session."
        )

    def compose_messages(
        self,
        context: ResolvedConversationContext,
        user_message: str,
        history: Iterable[ChatMessage] | None = None,
    ) -> list[ChatMessage]:
        if not user_message.strip():
            raise ValueError("user_message cannot be empty")

        messages: list[ChatMessage] = [
            {"role": "system", "content": self.compose_system_prompt(context)}
        ]

        clipped_history = list(history or [])[-self.config.max_history_turns :]
        for item in clipped_history:
            role = item.get("role")
            content = item.get("content", "")
            if role not in {"user", "assistant"}:
                continue
            if not isinstance(content, str) or not content.strip():
                continue
            messages.append({"role": role, "content": content.strip()})

        messages.append({"role": "user", "content": user_message.strip()})
        return messages

    def _format_memory_facts(self, facts: list[dict]) -> str:
        if not facts:
            return "- none"

        lines: list[str] = []
        for fact in facts[: self.config.max_memory_facts]:
            fact_text = self._safe_text(fact.get("fact"), "")
            if not fact_text:
                continue
            source = self._safe_text(fact.get("source"), "unknown")
            lines.append(f"- [{source}] {fact_text}")

        return "\n".join(lines) if lines else "- none"

    def _format_notes(self, notes: list[str]) -> str:
        if not notes:
            return "- none"
        lines = [f"- {note.strip()}" for note in notes[: self.config.max_memory_notes] if note.strip()]
        return "\n".join(lines) if lines else "- none"

    def _safe_text(self, value: object, default: str) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return default
