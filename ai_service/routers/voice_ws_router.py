"""
voice_ws_router.py — WSS /ws/voice/{session_id}: real-time voice via Pipecat.

CLAUDE.md's target voice architecture, built 2026-07-07:
    Browser mic ── streams ──> Sarvam Saaras v3 STT (streaming WS, native VAD)
        └─> OrchestratorTurnProcessor (the SAME run_chat_turn() as text chat)
              └─> Sarvam Bulbul v3 TTS (streaming WS) ── streams ──> browser

Unlike /voice/conversation/* (turn-based: record a full clip, upload, wait),
this is a live pipeline: audio flows continuously both ways, Sarvam's
server-side VAD decides when the citizen stopped talking (vad_signals=True —
CLAUDE.md's "Saaras V3 exclusive VAD"), and the reply starts speaking as
soon as it's synthesized. The turn-based endpoints stay as the fallback
for browsers/devices where live streaming fails.

The LLM stage is deliberately NOT a Pipecat LLM service: Pipecat wants to
own the LLM call, but our intelligence lives in the LangGraph orchestrator
(intent routing, 12 agents, profile learning, Mongo persistence).
OrchestratorTurnProcessor splices run_chat_turn() into the pipeline — voice
keeps full feature parity with text chat, and every turn persists to
conversation_sessions/reasoning_traces exactly like a typed one.

Auth: httpOnly access_token cookie on the handshake (same as
/ws/session/{id} — browsers can't set custom headers on WebSocket).
Invalid token → close 1008 before any audio is processed.
One concurrent voice session per citizen (CLAUDE.md rule) — a second
connection for the same citizen is refused with 1008.

Audio is processed in-memory only, never persisted (CLAUDE.md security
rule #6) — only the text transcript reaches Mongo, via run_chat_turn.

Wire protocol: Pipecat protobuf frames (audio/text/transcription) — pairs
with @pipecat-ai/client-js + @pipecat-ai/websocket-transport on the
frontend. The browser receives the citizen's own transcription frames and
the bot's text frames alongside the audio, so the chat UI can render the
conversation as it happens.
"""
import asyncio
import logging

from fastapi import APIRouter, HTTPException, WebSocket

from ai_service.db.mongo import ensure_indexes, get_db
from ai_service.graph.chat_turn import run_chat_turn
from ai_service.graph.session_summary import schedule_session_summary
from ai_service.utils.jwt_auth import citizen_id_from_websocket_cookies
from ai_service.utils.spring_client import fetch_citizen_profile

logger = logging.getLogger(__name__)
router = APIRouter(tags=["voice-websocket"])

_indexes_ready = False

# CLAUDE.md: "one concurrent voice session per userId enforced"
_active_voice_sessions: dict[str, str] = {}  # citizen_id -> session_id


def _build_orchestrator_processor(db, citizen_id: str, session_id: str, profile: dict, lang: str):
    """Builds the custom FrameProcessor that replaces Pipecat's LLM stage.

    Buffers TranscriptionFrames during a user turn; when Sarvam's VAD says
    the citizen stopped speaking, runs the buffered transcript through
    run_chat_turn() (spawned as a task so system frames keep flowing) and
    pushes the reply as a TTSSpeakFrame for Bulbul to voice. If the citizen
    starts speaking again while a turn is still processing, the in-flight
    turn is cancelled — their newer utterance wins.
    """
    from pipecat.frames.frames import (
        Frame,
        InterimTranscriptionFrame,
        TranscriptionFrame,
        TTSSpeakFrame,
        UserStartedSpeakingFrame,
        UserStoppedSpeakingFrame,
    )
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

    class OrchestratorTurnProcessor(FrameProcessor):
        # Sarvam's FINAL transcript arrives ~0.5s AFTER its VAD emits
        # UserStoppedSpeakingFrame (measured in the real e2e test, not
        # assumed) — so firing the turn directly on the stop event sees an
        # empty buffer. Instead, both the stop event and each transcription
        # (re)arm a short debounce; the turn fires once the transcript has
        # settled. A new utterance cancels everything (barge-in).
        DEBOUNCE_SECS = 0.8

        def __init__(self):
            super().__init__()
            self._buffer: list[str] = []
            self._turn_task: asyncio.Task | None = None
            self._debounce_task: asyncio.Task | None = None
            self._user_speaking = False

        def _cancel(self, task: asyncio.Task | None):
            if task and not task.done():
                task.cancel()

        def _arm_debounce(self):
            self._cancel(self._debounce_task)
            self._debounce_task = asyncio.create_task(self._debounced_fire())

        async def _debounced_fire(self):
            await asyncio.sleep(self.DEBOUNCE_SECS)
            text = " ".join(self._buffer).strip()
            self._buffer.clear()
            if text:
                self._turn_task = asyncio.create_task(self._run_turn(text))

        async def process_frame(self, frame: Frame, direction: FrameDirection):
            await super().process_frame(frame, direction)

            if isinstance(frame, UserStartedSpeakingFrame):
                # Citizen speaking (again) — newest utterance supersedes any
                # pending debounce or in-flight turn (barge-in).
                self._user_speaking = True
                self._cancel(self._debounce_task)
                self._cancel(self._turn_task)

            elif isinstance(frame, TranscriptionFrame):
                if frame.text and frame.text.strip():
                    self._buffer.append(frame.text.strip())
                    if not self._user_speaking:
                        self._arm_debounce()  # late final after VAD stop

            elif isinstance(frame, UserStoppedSpeakingFrame):
                self._user_speaking = False
                self._arm_debounce()

            # Pass everything through (audio to output, transcriptions to the
            # browser for live captions, system frames onward).
            await self.push_frame(frame, direction)

        async def _run_turn(self, text: str):
            try:
                result = await run_chat_turn(
                    db, citizen_id=citizen_id, session_id=session_id,
                    message=text, channel="voice", lang=lang, profile=profile,
                )
                reply = (result.get("reply") or "").strip()
                if reply:
                    await self.push_frame(TTSSpeakFrame(reply))
            except asyncio.CancelledError:
                logger.info("[VOICE] turn cancelled (citizen spoke again) session=%s", session_id)
                raise
            except Exception:
                logger.exception("[VOICE] orchestrator turn failed session=%s", session_id)
                await self.push_frame(TTSSpeakFrame(
                    "Maafi kijiye, kuch gadbad ho gayi. Kripya dobara boliye."
                ))

    return OrchestratorTurnProcessor()


@router.websocket("/ws/voice/{session_id}")
async def voice_ws(websocket: WebSocket, session_id: str):
    global _indexes_ready

    try:
        citizen_id = citizen_id_from_websocket_cookies(websocket.cookies)
    except HTTPException as e:
        await websocket.accept()
        await websocket.close(code=1008, reason=e.detail)
        return

    if citizen_id in _active_voice_sessions:
        await websocket.accept()
        await websocket.close(code=1008, reason="Voice session already active for this citizen.")
        return

    await websocket.accept()
    _active_voice_sessions[citizen_id] = session_id

    db = get_db()
    if not _indexes_ready:
        await ensure_indexes()
        _indexes_ready = True

    try:
        # Heavy imports deferred: pipecat + its deps load ~2s; only voice
        # connections pay that cost, not every worker start.
        import os

        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.runner import PipelineRunner
        from pipecat.pipeline.task import PipelineParams, PipelineTask
        from pipecat.serializers.protobuf import ProtobufFrameSerializer
        from pipecat.services.sarvam.stt import SarvamSTTService
        from pipecat.services.sarvam.tts import SarvamTTSService
        from pipecat.transcriptions.language import Language
        from pipecat.transports.websocket.fastapi import (
            FastAPIWebsocketParams,
            FastAPIWebsocketTransport,
        )

        from ai_service.utils.sarvam import get_language_for_state

        api_key = os.getenv("SARVAM_API_KEY", "").strip()
        if not api_key:
            await websocket.close(code=1011, reason="Voice not configured (SARVAM_API_KEY missing).")
            return

        profile = await fetch_citizen_profile(citizen_id)
        # TTS voice language follows the citizen's state for now (v1
        # simplification — STT auto-detects per utterance, but Bulbul's
        # target language is fixed per connection).
        lang_2char = get_language_for_state(profile.get("state"))

        transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                add_wav_header=False,
                serializer=ProtobufFrameSerializer(),
            ),
        )

        stt = SarvamSTTService(
            api_key=api_key,
            model="saaras:v3",
            mode="transcribe",  # CLAUDE.md: always explicit, even though it's the default
            params=SarvamSTTService.InputParams(
                vad_signals=True,  # Sarvam's server-side VAD drives turn-taking
            ),
        )

        tts = SarvamTTSService(
            api_key=api_key,
            model="bulbul:v3",
            params=SarvamTTSService.InputParams(
                pace=1.0,  # bulbul:v3 supports pace + temperature ONLY (no pitch/loudness)
                language=Language(lang_2char) if lang_2char in Language._value2member_map_ else Language.HI,
            ),
        )

        orchestrator_stage = _build_orchestrator_processor(
            db, citizen_id, session_id, profile, lang_2char
        )

        pipeline = Pipeline([
            transport.input(),
            stt,
            orchestrator_stage,
            tts,
            transport.output(),
        ])

        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                audio_in_sample_rate=16000,   # Sarvam STT requirement
                audio_out_sample_rate=24000,  # Bulbul-supported output rate
            ),
        )

        logger.info("[VOICE] live session %s connected (citizen %s, lang %s)",
                    session_id, citizen_id, lang_2char)
        runner = PipelineRunner(handle_sigint=False)
        await runner.run(task)

    except Exception:
        logger.exception("[VOICE] live session %s crashed", session_id)
    finally:
        _active_voice_sessions.pop(citizen_id, None)
        schedule_session_summary(db, session_id)
        logger.info("[VOICE] live session %s ended", session_id)
