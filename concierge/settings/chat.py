"""Settings for the Chat application."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict

# Sentinel value of ``CHAT_BOT_AGENT_TYPE`` that selects the streaming Foundry
# responder. Anything else is resolved against the shared AgentRegistry.
FOUNDRY_BOT_AGENT_TYPE = "foundry"

# Default system prompt used by the accessibility (deafblind) realtime mode.
# The realtime API has no speech-rate parameter, so "speak slowly" can only be
# requested here via instructions. It also biases the model toward short,
# concrete, one-idea-at-a-time explanations for users who find concept
# formation difficult, and points it at the ``capture_image`` camera tool.
_DEFAULT_ACCESSIBLE_SYSTEM_PROMPT = (
    "あなたは盲ろう者を支援する Concierge の音声アシスタントです。次を必ず守ってください。"
    "(1) 短い文で、ゆっくり、はっきり、区切って話す。"
    "(2) 一度に一つのことだけ伝える。"
    "(3) 専門用語や比喩を避け、身近で具体的な例を使って、概念をかみ砕いて説明する。"
    "(4) 相手が理解できたかをこまめに確認しながら進める。"
    "(5) 画像や周囲の状況を説明するときは、色・形・位置・数などを具体的に言葉にする。"
    "(6) ユーザーが写真撮影や周囲の確認を求めたら capture_image ツールを使い、撮れた画像を丁寧に説明する。"
)


class ChatRepositoryBackend(str, Enum):
    MEMORY = "memory"
    POSTGRES = "postgres"
    AZURE_POSTGRES = "azure-postgres"


class ChatSettings(BaseSettings):
    repository_backend: ChatRepositoryBackend = ChatRepositoryBackend.MEMORY
    conversations_table_name: str = "chat_conversations"
    participants_table_name: str = "chat_participants"
    messages_table_name: str = "chat_messages"

    bot_participant_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    bot_display_name: str = "Concierge AI"
    bot_history_limit: int = 20
    bot_system_prompt: str = "あなたは Concierge Chat のアシスタントです。日本語で簡潔に応答してください。"
    bot_model: str = "azure_ai:gpt-5"

    # Selects the chat reply responder. ``foundry`` (default) uses the streaming
    # ``FoundryChatbotResponder`` (requires ``AZURE_AI_PROJECT_ENDPOINT``). Any
    # other value is resolved against the shared ``AgentRegistry`` (built-ins:
    # ``echo``, ``langgraph``, ``github-copilot-sdk``, ``microsoft-agent-framework``).
    bot_agent_type: str = FOUNDRY_BOT_AGENT_TYPE

    realtime_model: str = "gpt-realtime-1.5"
    realtime_voice: str = "alloy"
    realtime_locale: str = "ja-JP"
    realtime_system_prompt: str = "あなたは Concierge Chat のアシスタントです。日本語で簡潔に応答してください。"
    realtime_audio_sample_rate_hz: int = 24000
    realtime_max_session_seconds: int = 600
    # Optional Azure deployment name used for input-audio transcription. When
    # empty (default), the ``transcription`` block is omitted from
    # ``session.update`` and Foundry will not transcribe the user's audio
    # (assistant speech still works). The default OpenAI model id
    # ``gpt-4o-mini-transcribe`` does not correspond to an Azure deployment in
    # most resources, so leaving this empty avoids silent failures.
    realtime_transcription_model: str = ""

    # --- Realtime turn detection (VAD) tuning ---
    # Controls how eagerly the model decides the user has finished speaking and
    # starts replying. This is the knob to turn when "the AI cuts in as soon as
    # I pause". Type can be:
    # - ``server_vad``  : silence-based detection (tune threshold / padding /
    #                     silence_duration below). Universally supported.
    # - ``semantic_vad``: the model decides from sentence semantics and is much
    #                     less likely to interrupt mid-thought. Pair with
    #                     ``realtime_vad_eagerness`` (use ``low`` to let the user
    #                     finish). Recommended fix for premature responses.
    # - ``none``        : push-to-talk; the client must commit the buffer and
    #                     send ``response.create`` itself (no auto turn-taking).
    realtime_turn_detection_type: str = "server_vad"
    # ``server_vad`` activation threshold (0.0-1.0). Higher needs louder speech
    # to trigger, which helps in noisy rooms.
    realtime_vad_threshold: float = 0.5
    # ``server_vad`` audio (ms) retained before detected speech start.
    realtime_vad_prefix_padding_ms: int = 300
    # ``server_vad`` silence (ms) required before the turn is considered over.
    # Raised above the API default (~200-500 ms) so brief thinking pauses no
    # longer make the model jump in.
    realtime_vad_silence_duration_ms: int = 700
    # ``semantic_vad`` eagerness: ``low`` | ``medium`` | ``high`` | ``auto``.
    # ``low`` lets the user take their time before the model responds.
    realtime_vad_eagerness: str = "low"
    # Whether the model auto-generates a response when a turn ends. Set to
    # ``False`` to require an explicit ``response.create`` (server-side
    # moderation / manual gating). Applies to ``server_vad`` and ``semantic_vad``.
    realtime_vad_create_response: bool = True
    # Whether new user speech interrupts (barges in on) an in-progress response.
    realtime_vad_interrupt_response: bool = True

    # --- Accessibility (deafblind) mode ---
    # System prompt applied when the realtime WebSocket is opened with
    # ``?mode=accessible`` (the ``/accessible`` minimal UI). Overrides
    # ``realtime_system_prompt`` for that session only. See
    # ``_DEFAULT_ACCESSIBLE_SYSTEM_PROMPT`` for the rationale.
    realtime_accessible_system_prompt: str = _DEFAULT_ACCESSIBLE_SYSTEM_PROMPT
    # Default browser Text-to-Speech playback rate for the accessible UI's
    # optional read-aloud (``SpeechSynthesisUtterance.rate``; 0.1-10, 1.0 is
    # normal). Kept below 1.0 so synthesized speech is easier to follow. Only
    # affects browser TTS — the realtime voice cannot be rate-controlled.
    accessible_tts_rate: float = 0.85
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="CHAT_",
        extra="ignore",
    )


@lru_cache
def get_chat_settings() -> ChatSettings:
    return ChatSettings()
