# Run-dino
# Dino Race — Telegram Bot (3-player race, leaderboard, owner podcast)

## Features
- Solo or up-to-3-player race (tick-based).
- Inline buttons to jump (each player has their own button).
- Leaderboard stored in SQLite (`dino.db`).
- Owner-only features:
  - `/broadcast <text>` — send text to all known chats.
  - `/podcast` — send this command, then send an audio/voice/document; bot forwards it to all chats.
  - `/shutdown` — stop the bot and all games.
- Simple rendering using PIL; frames sent as images.

## Setup (local)
1. Clone repo.
2. Create venv:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
