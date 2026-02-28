from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Protocol

from .context_resolver import ResolvedConversationContext
from .prompt_composer import ChatMessage, PromptComposer


class ChatBackendProtocol(Protocol):
    def chat(self, messages: list[ChatMessage]) -> str: ...

    def stream_chat(self, messages: list[ChatMessage]) -> Iterator[str]: ...


@dataclass
class BranchConversationSession:
    """In-memory branch chat session, no persistence side effects."""

    context: ResolvedConversationContext
    composer: PromptComposer
    client: ChatBackendProtocol
    history: list[ChatMessage] = field(default_factory=list)

    def reset(self) -> None:
        self.history.clear()

    def reply(self, user_message: str) -> str:
        messages = self.composer.compose_messages(
            context=self.context,
            user_message=user_message,
            history=self.history,
        )
        assistant_text = self.client.chat(messages).strip()
        if not assistant_text:
            raise RuntimeError("Received empty assistant response")
        self._append_turn(user_message.strip(), assistant_text)
        return assistant_text

    def stream_reply(self, user_message: str) -> Iterator[str]:
        messages = self.composer.compose_messages(
            context=self.context,
            user_message=user_message,
            history=self.history,
        )

        user_text = user_message.strip()
        chunks: list[str] = []
        for chunk in self.client.stream_chat(messages):
            if not chunk:
                continue
            chunks.append(chunk)
            yield chunk

        assistant_text = "".join(chunks).strip()
        if not assistant_text:
            raise RuntimeError("Received empty assistant response from stream")

        self._append_turn(user_text, assistant_text)

    def describe_context(self) -> dict[str, str | int]:
        self_card = self.context.self_card
        return {
            "session_id": self.context.session_id,
            "branch_name": self.context.branch_name,
            "self_name": str(self_card.get("name", "Future Self")),
            "optimization_goal": str(self_card.get("optimizationGoal", "")),
            "worldview": str(self_card.get("worldview", "")),
            "trade_off": str(self_card.get("tradeOff", "")),
            "memory_facts": len(self.context.memory_facts),
            "memory_notes": len(self.context.memory_notes),
            "history_messages": len(self.history),
        }

    def _append_turn(self, user_text: str, assistant_text: str) -> None:
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": assistant_text})
