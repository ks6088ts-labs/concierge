"""Direct Foundry realtime WS probe (no FastAPI). Used to diagnose audio routing."""

from __future__ import annotations

import base64
import json
import math
import os
import struct
import threading
import time

import websockets.sync.client as ws_sync
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

SR = 24000


def pcm(seconds: float, hz: float, amp: float = 0.5) -> bytes:
    n = int(SR * seconds)
    buf = bytearray()
    for i in range(n):
        v = int(amp * 32767 * math.sin(2 * math.pi * hz * i / SR))
        buf += struct.pack("<h", v)
    return bytes(buf)


def main() -> None:
    endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT_REALTIME"]
    deployment = os.environ.get("CHAT_REALTIME_MODEL", "gpt-realtime-1.5")
    host = endpoint.split("https://", 1)[1].split("/", 1)[0]
    if host.endswith(".services.ai.azure.com"):
        host = host.split(".")[0] + ".openai.azure.com"
    wss_url = f"wss://{host}/openai/v1/realtime?model={deployment}"

    token = DefaultAzureCredential().get_token("https://cognitiveservices.azure.com/.default").token
    conn = ws_sync.connect(wss_url, additional_headers={"Authorization": f"Bearer {token}"})

    events: list[str] = []

    def reader() -> None:
        for raw in conn:
            m = json.loads(raw)
            t = m.get("type", "")
            events.append(t)
            interesting = (
                "audio" in t.lower() or "error" in t or t.endswith(".committed") or "speech" in t or "transcrip" in t
            )
            if interesting:
                print(f"  ◀ {t:55s} {json.dumps(m, ensure_ascii=False)[:240]}")

    threading.Thread(target=reader, daemon=True).start()

    session_config = {
        "type": "realtime",
        "instructions": "You are a helpful assistant.",
        "audio": {
            "input": {
                "format": {"type": "audio/pcm", "rate": 24000},
                "turn_detection": {"type": "server_vad"},
                "transcription": {"model": "gpt-4o-mini-transcribe", "language": "ja"},
            },
            "output": {
                "format": {"type": "audio/pcm", "rate": 24000},
                "voice": "alloy",
            },
        },
    }
    conn.send(json.dumps({"type": "session.update", "session": session_config}))
    time.sleep(1.5)

    tone = pcm(0.2, 440.0, amp=0.7)
    for _ in range(10):
        conn.send(json.dumps({"type": "input_audio_buffer.append", "audio": base64.b64encode(tone).decode()}))
        time.sleep(0.05)

    print("--- 2s of audio sent, committing ---")
    conn.send(json.dumps({"type": "input_audio_buffer.commit"}))
    time.sleep(5)
    print()
    print("=== events ===")
    print(events)
    conn.close()


if __name__ == "__main__":
    main()
