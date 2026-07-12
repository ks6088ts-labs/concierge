"""Single-file voice-button web app for users who find speaking difficult.

Hybrid strategy:
  * If a button entry has ``"file"``, the server streams the audio file from
    ``--voices-dir`` (default: ``./voices``) and the browser plays it.
  * Otherwise the browser uses the Web Speech API (``speechSynthesis``) with
    the entry's ``"text"`` — no audio files required to get started.

The config (JSON) and the served HTML are both produced by this one file.

Run locally::

    python scripts/playgrounds/tts.py
    python scripts/playgrounds/tts.py --config scripts/playgrounds/tts_config.example.json
    python scripts/playgrounds/tts.py --host 0.0.0.0 --port 8000 --voices-dir ./voices

Run in Docker (reuses the repo Dockerfile)::

    docker build -t concierge .
    docker run --rm -p 8000:8000 concierge \\
        python scripts/playgrounds/tts.py --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict[str, Any] = {
    "title": "つたえるボタン",
    "lang": "ja-JP",
    "rate": 1.0,
    "pitch": 1.0,
    "items": [
        {"id": "thanks", "label": "ありがとう", "emoji": "🙏", "text": "ありがとう"},
        {"id": "love", "label": "大好きだよ", "emoji": "❤️", "text": "大好きだよ"},
        {"id": "want_do", "label": "これをやりたい", "emoji": "✨", "text": "これをやりたい"},
        {"id": "want_together", "label": "一緒にやりたい", "emoji": "🤝", "text": "一緒にやりたい"},
        {"id": "tasty", "label": "おいしい", "emoji": "🍴", "text": "おいしい"},
        {"id": "happy", "label": "うれしい", "emoji": "😊", "text": "うれしい"},
        {"id": "hungry", "label": "お腹がすいた", "emoji": "🍙", "text": "お腹がすいた"},
        {"id": "toilet", "label": "トイレに行きたい", "emoji": "🚻", "text": "トイレに行きたい"},
    ],
}


INDEX_HTML = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
  <title>__TITLE__</title>
  <style>
    :root { color-scheme: light dark; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Sans",
                   "Noto Sans JP", sans-serif;
      background: #fafafa;
      color: #222;
      min-height: 100vh;
    }
    @media (prefers-color-scheme: dark) {
      body { background: #1a1a1a; color: #eee; }
    }
    header {
      padding: 16px 20px;
      text-align: center;
      font-size: 1.25rem;
      font-weight: 600;
      border-bottom: 1px solid rgba(127,127,127,0.2);
    }
    main {
      padding: 16px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 14px;
      max-width: 960px;
      margin: 0 auto;
    }
    .custom-panel {
      max-width: 960px;
      margin: 16px auto 0;
      padding: 0 16px;
    }
    .custom-form {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: stretch;
    }
    .custom-form label {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
    #custom-text {
      width: 100%;
      min-height: 76px;
      resize: vertical;
      border: 1px solid rgba(127,127,127,0.35);
      border-radius: 14px;
      padding: 14px 16px;
      font: inherit;
      font-size: 1rem;
      line-height: 1.5;
      background: rgba(255,255,255,0.85);
      color: inherit;
    }
    #custom-text:focus-visible,
    button:focus-visible {
      outline: 3px solid rgba(79,140,255,0.45);
      outline-offset: 2px;
    }
    .custom-play {
      appearance: none;
      border: none;
      border-radius: 14px;
      padding: 0 22px;
      min-width: 112px;
      font-size: 1rem;
      font-weight: 700;
      color: #fff;
      background: linear-gradient(135deg, #0f8f7a, #2d72d9);
      box-shadow: 0 4px 14px rgba(0,0,0,0.12);
      cursor: pointer;
      transition: transform 80ms ease, box-shadow 80ms ease, filter 120ms ease;
      touch-action: manipulation;
      -webkit-tap-highlight-color: transparent;
    }
    .custom-play:active { transform: scale(0.97); }
    .custom-play.playing { filter: brightness(1.15); box-shadow: 0 0 0 4px rgba(15,143,122,0.35); }
    @media (prefers-color-scheme: dark) {
      #custom-text { background: rgba(34,34,34,0.92); }
    }
    @media (max-width: 520px) {
      .custom-form { grid-template-columns: 1fr; }
      .custom-play { min-height: 56px; }
    }
    button.tile {
      appearance: none;
      border: none;
      border-radius: 18px;
      padding: 28px 12px;
      font-size: 1.15rem;
      font-weight: 600;
      line-height: 1.4;
      color: #fff;
      background: linear-gradient(135deg, #4f8cff, #6a5cff);
      box-shadow: 0 4px 14px rgba(0,0,0,0.12);
      cursor: pointer;
      transition: transform 80ms ease, box-shadow 80ms ease, filter 120ms ease;
      min-height: 120px;
      touch-action: manipulation;
      -webkit-tap-highlight-color: transparent;
    }
    button.tile:active { transform: scale(0.97); }
    button.tile.playing { filter: brightness(1.15); box-shadow: 0 0 0 4px rgba(106,92,255,0.4); }
    button.tile .emoji { display: block; font-size: 2rem; margin-bottom: 6px; }
    footer {
      padding: 12px 20px 24px;
      text-align: center;
      font-size: 0.85rem;
      opacity: 0.6;
    }
    #status {
      text-align: center;
      min-height: 1.4em;
      padding: 4px 0;
      font-size: 0.9rem;
      opacity: 0.8;
    }
  </style>
</head>
<body>
  <header>__TITLE__</header>
  <div id="status"></div>
  <section class="custom-panel" aria-label="自由入力の読み上げ">
    <form id="custom-form" class="custom-form">
      <label for="custom-text">読み上げたい文字列</label>
      <textarea id="custom-text" maxlength="4000" rows="3" placeholder="読み上げたい文字を入力"></textarea>
      <button id="custom-play" class="custom-play" type="submit">再生</button>
    </form>
  </section>
  <main id="grid"></main>
  <footer>ボタンを押すと音声が再生されます</footer>

  <script>
    const statusEl = document.getElementById("status");
    const grid = document.getElementById("grid");
    const customForm = document.getElementById("custom-form");
    const customText = document.getElementById("custom-text");
    const customPlay = document.getElementById("custom-play");
    const CUSTOM_TEXT_MAX_LENGTH = 4000;
    let currentAudio = null;
    let config = null;

    function setStatus(msg) { statusEl.textContent = msg || ""; }

    function stopAll() {
      if (currentAudio) { currentAudio.pause(); currentAudio.currentTime = 0; currentAudio = null; }
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      document.querySelectorAll(".playing").forEach(el => el.classList.remove("playing"));
    }

    function playFile(item, btn) {
      const url = "voices/" + encodeURIComponent(item.file);
      const audio = new Audio(url);
      currentAudio = audio;
      btn.classList.add("playing");
      audio.addEventListener("ended", () => btn.classList.remove("playing"));
      audio.addEventListener("error", () => {
        btn.classList.remove("playing");
        setStatus("音声ファイルを再生できません: " + item.file);
      });
      audio.play().catch(err => {
        btn.classList.remove("playing");
        setStatus("再生エラー: " + err.message);
      });
    }

    function speakText(text, btn) {
      if (!("speechSynthesis" in window)) {
        setStatus("このブラウザは音声合成に対応していません");
        return;
      }
      const speechConfig = config || {};
      const u = new SpeechSynthesisUtterance(text);
      u.lang = speechConfig.lang || "ja-JP";
      if (typeof speechConfig.rate === "number") u.rate = speechConfig.rate;
      if (typeof speechConfig.pitch === "number") u.pitch = speechConfig.pitch;
      btn.classList.add("playing");
      u.onend = () => btn.classList.remove("playing");
      u.onerror = () => { btn.classList.remove("playing"); setStatus("音声合成に失敗しました"); };
      window.speechSynthesis.speak(u);
    }

    function handleClick(item, btn) {
      stopAll();
      setStatus("");
      if (item.file) { playFile(item, btn); }
      else if (item.text) { speakText(item.text, btn); }
      else { setStatus("この項目には text も file も指定されていません"); }
    }

    function handleCustomSubmit(event) {
      event.preventDefault();
      const text = customText.value.trim();
      stopAll();
      if (!text) {
        setStatus("読み上げたい文字列を入力してください");
        customText.focus();
        return;
      }
      if (text.length > CUSTOM_TEXT_MAX_LENGTH) {
        setStatus("読み上げられる文字列は4000文字までです");
        customText.focus();
        return;
      }
      setStatus("");
      speakText(text, customPlay);
    }

    function render(cfg) {
      config = cfg;
      document.title = cfg.title || "つたえるボタン";
      document.querySelectorAll("header").forEach(h => h.textContent = cfg.title || document.title);
      grid.innerHTML = "";
      for (const item of cfg.items || []) {
        const btn = document.createElement("button");
        btn.className = "tile";
        btn.type = "button";
        const emoji = item.emoji ? `<span class="emoji">${item.emoji}</span>` : "";
        btn.innerHTML = `${emoji}<span>${item.label || item.id || ""}</span>`;
        btn.addEventListener("click", () => handleClick(item, btn));
        grid.appendChild(btn);
      }
    }

    customForm.addEventListener("submit", handleCustomSubmit);

    fetch("config")
      .then(r => r.json())
      .then(render)
      .catch(err => setStatus("設定の取得に失敗: " + err.message));
  </script>
</body>
</html>
"""


def _load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        logger.info("Using built-in default config")
        return DEFAULT_CONFIG
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    if not isinstance(cfg, dict) or "items" not in cfg:
        raise ValueError("Config must be a JSON object containing an 'items' array")
    return cfg


def create_app(config_path: Path | None = None, voices_dir: Path | None = None) -> FastAPI:
    cfg = _load_config(config_path)
    app = FastAPI(title=cfg.get("title", "voice-buttons"))
    html = INDEX_HTML.replace("__TITLE__", cfg.get("title", "つたえるボタン"))

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse(html)

    @app.get("/config")
    def get_config() -> JSONResponse:
        return JSONResponse(cfg)

    if voices_dir is not None:
        voices_dir = voices_dir.resolve()
        if not voices_dir.exists():
            logger.warning("voices_dir does not exist: %s (text-only items will still work)", voices_dir)
            voices_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/voices", StaticFiles(directory=str(voices_dir)), name="voices")
    else:

        @app.get("/voices/{name}")
        def _no_voices(name: str) -> None:  # pragma: no cover - trivial
            raise HTTPException(status_code=404, detail="voices-dir is not configured")

    return app


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single-file voice-button web app")
    parser.add_argument("--config", type=Path, default=None, help="Path to JSON config file")
    parser.add_argument("--voices-dir", type=Path, default=None, help="Directory containing audio files")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (use 0.0.0.0 in Docker)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--log-level", default="info", help="uvicorn log level")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    args = _parse_args(argv)
    import uvicorn

    app = create_app(config_path=args.config, voices_dir=args.voices_dir)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)


if __name__ == "__main__":
    main(sys.argv[1:])
