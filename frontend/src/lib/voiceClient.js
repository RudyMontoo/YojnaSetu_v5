// voiceClient.js — live real-time voice call to /ws/voice/{session_id}
// (Pipecat protobuf protocol: streaming mic in, streaming reply audio out,
// live transcripts both ways, barge-in interruption).
//
// Pairs with ai_service/routers/voice_ws_router.py: browser mic streams
// continuously, Sarvam's server-side VAD decides when the citizen stopped
// talking, the transcript runs through the SAME 12-agent orchestrator as
// text chat (one shared session thread), and the spoken reply streams back
// as it's synthesized. Auth is the same httpOnly JWT cookie as everything
// else — cookies ride the WebSocket handshake automatically on same-origin.
//
// The PipecatClient owns the microphone and audio playback internally
// (getUserMedia + Web Audio); callers just react to events.

import { PipecatClient } from "@pipecat-ai/client-js";
import {
  ProtobufFrameSerializer,
  WebSocketTransport,
} from "@pipecat-ai/websocket-transport";

export function createVoiceClient({
  sessionId,
  onUserTranscript,   // ({ text, final }) — live captions of what the citizen is saying
  onBotText,          // (text) — chunks of the bot's spoken reply, as it speaks
  onUserSpeaking,     // (bool)
  onBotSpeaking,      // (bool)
  onDisconnected,     // () — call ended (either side)
  onError,            // (message)
}) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const wsUrl = `${proto}://${window.location.host}/ws/voice/${sessionId}`;

  const transport = new WebSocketTransport({
    wsUrl,
    serializer: new ProtobufFrameSerializer(),
    recorderSampleRate: 16000, // Sarvam STT requirement
    playerSampleRate: 24000,   // matches backend audio_out_sample_rate
  });

  const client = new PipecatClient({
    transport,
    enableMic: true,
    callbacks: {
      onUserTranscript: (data) => onUserTranscript?.(data),
      onBotTtsText: (data) => onBotText?.(data?.text ?? ""),
      onUserStartedSpeaking: () => onUserSpeaking?.(true),
      onUserStoppedSpeaking: () => onUserSpeaking?.(false),
      onBotStartedSpeaking: () => onBotSpeaking?.(true),
      onBotStoppedSpeaking: () => onBotSpeaking?.(false),
      onDisconnected: () => onDisconnected?.(),
      onError: (msg) => onError?.(msg?.data?.message || "Voice connection error"),
    },
  });

  return client;
}
