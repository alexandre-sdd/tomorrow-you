"""Engine modules for Future Selves."""

from .context_resolver import ContextResolver, ContextResolutionError, ResolvedConversationContext
from .conversation_memory import (
    analyze_and_persist_transcript_insights,
    append_conversation_turn,
)
from .conversation_session import BranchConversationSession
from .current_self_auto_generator import (
    CurrentSelfAutoGeneratorEngine,
    CurrentSelfGenerationContext,
    CurrentSelfGenerationResult,
)
from .mistral_client import MistralChatClient, MistralChatConfig, MistralClientError
from .profile_extractor import (
    ExtractionContext,
    ExtractionResult,
    ProfileExtractorEngine,
)
from .prompt_composer import PromptComposer, PromptComposerConfig

__all__ = [
    "ContextResolver",
    "ContextResolutionError",
    "ResolvedConversationContext",
    "append_conversation_turn",
    "analyze_and_persist_transcript_insights",
    "PromptComposer",
    "PromptComposerConfig",
    "MistralChatClient",
    "MistralChatConfig",
    "MistralClientError",
    "BranchConversationSession",
    "ProfileExtractorEngine",
    "ExtractionContext",
    "ExtractionResult",
    "CurrentSelfAutoGeneratorEngine",
    "CurrentSelfGenerationContext",
    "CurrentSelfGenerationResult",
]
