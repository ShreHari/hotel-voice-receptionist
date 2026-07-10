# Aria - AI Voice Receptionist for The Grandview Hotel

An AI-powered voice receptionist built for the NexCell Solutions AI Intern technical assessment. Aria handles hotel conversations end to end: she checks availability, searches rooms by guest preferences, creates and cancels bookings, and answers hotel FAQs. Every external action goes through a real MCP (Model Context Protocol) server.

**Live deployment:** https://aria-hotel-receptionist.onrender.com (free tier, so the first load after idle can take up to a minute to wake; use Chrome for voice)

Built by Shre Hari Prem Anandh.

## Architecture

```
 Browser (Chrome)
 ├─ Web Speech API: speech to text (mic) and text to speech (replies)
 └─ single page UI: transcript + MCP tool activity chips
        │  POST /chat { session_id, message }
        ▼
 FastAPI backend (app/main.py)
        │
        ▼
 Agent loop (app/agent.py, hand-written, no framework)
        │  1. gpt-4o-mini reasons over the conversation
        │  2. if it needs facts or actions it requests a tool
        │  3. the tool call is executed over MCP
        │  4. the result is fed back to the model
        │  5. loop until the model produces a final spoken reply
        ▼
 MCP client bridge (app/mcp_client.py)
        │  Model Context Protocol over stdio
        ▼
 MCP server (mcp_server/server.py, FastMCP)
        │  5 tools: check_availability, search_rooms,
        │  create_booking, cancel_booking, faq_search
        ▼
 SQLite (data/hotel.db: rooms, bookings, faqs)
```

The key design point: the LLM never touches the database directly. It can only act on the world through MCP tools, which is what makes the behaviour inspectable and safe. The UI shows a chip for every MCP tool used on each turn, so you can watch the agent think.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI + Python 3.12 | suggested stack, async end to end |
| Agent | Hand-written loop over OpenAI gpt-4o-mini | every step visible and explainable, no framework magic |
| Tools | MCP Python SDK (FastMCP server + stdio client) | real protocol, not renamed function calling |
| Voice in | Browser Web Speech API (mic) | free, zero keys, works in any Chrome |
| Voice out | OpenAI neural TTS, browser voice as automatic fallback | natural speech quality; the demo still works even if TTS is unavailable |
| Database | SQLite | zero setup, easy to inspect and reseed |
| Frontend | Single static page, vanilla JS | nothing to build, loads instantly |

## Implemented MCP tools (5)

1. `check_availability(check_in, check_out)` - rooms free for a date range, checked against confirmed bookings
2. `search_rooms(max_price, view, quiet_only, accessible_only, min_floor)` - preference search used for recommendations
3. `create_booking(guest_name, room_number, check_in, check_out)` - books a room, detects date clashes, returns a reference and total price
4. `cancel_booking(reference)` - cancels by reference with sensible error messages
5. `faq_search(query)` - keyword-scored search over hotel FAQs (check-in times, breakfast, parking, pets, cancellation policy)

## Run it locally

Requires Python 3.12 and Chrome (the Web Speech API needs Chrome or Edge).

```bash
git clone https://github.com/ShreHari/hotel-voice-receptionist.git
cd hotel-voice-receptionist
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env        # then put your OpenAI API key in .env
./run.sh                    # seeds the database, starts the server, opens Chrome
```

Or manually: `./.venv/bin/uvicorn app.main:app --port 8100` and open http://localhost:8100.

### Or run it with Docker (bonus)

```bash
cp .env.example .env        # put your OpenAI API key in .env
docker compose up --build
```

Then open http://localhost:8100. The image is a multi-stage build (about 288 MB), runs as a non-root user, ships the MCP server inside the same container, and has a Python-based healthcheck (the slim image has no curl). The API key is injected at runtime via env_file and is never baked into the image.

Click the mic and say, for example:
- "Do you have a quiet room with a park view under 160 pounds?"
- "Book it please, my name is Alex Carter, August 1st to 3rd."
- "What is your cancellation policy?"

## Design decisions and trade-offs

- **No agent framework.** LangChain and LangGraph are great, but for an assessment the point is to show I understand the agent loop itself: model, tool call, execution, result, repeat. It is about 60 lines and fully mine.
- **Hybrid voice layer.** The mic uses the browser's Web Speech API (free, zero setup), while Aria's replies are synthesised server-side with OpenAI TTS for natural voice quality. If the TTS endpoint is ever unavailable, the page automatically falls back to the browser voice, so the demo cannot lose its voice. This swap also demonstrates the point of keeping voice at the edge: adding neural TTS touched one endpoint and one frontend function, and zero lines of the agent, MCP, or database.
- **Conversation memory** is per-session, in process, trimmed to the last 30 messages. Enough for a receptionist conversation; a production version would move sessions to Redis.
- **Voice-first prompting.** The system prompt forbids lists and markdown and forces prices to be spoken in pounds, because the replies are read aloud by TTS.
- **Errors are part of the UX.** If a booking clashes, the tool returns a structured error and Aria explains it and offers an alternative instead of failing.

## How this evolved during the build

A few things changed along the way, usually because testing proved me wrong about something:

- **Voice output got upgraded.** I started with the browser's built-in voice everywhere, to keep the demo free and zero-setup. It worked, but it sounded robotic, and voice quality is one of the evaluation criteria. So replies now go through OpenAI TTS on the server, with the browser voice kept as an automatic fallback so voice output can never fully break.
- **The welcome screen exists because browsers made me add it.** I wanted Aria to greet guests out loud the moment the page loads. Browsers block audio before the first click, so the page now opens with a start screen, and that one click unlocks the audio. It ended up being a nicer opening anyway, it feels like answering a call.
- **The mic now reopens after Aria finishes speaking.** Early versions needed a click before every sentence, which felt clunky in testing. Now the conversation is hands free: she answers, the mic opens, you talk. If you stay quiet, recognition just times out.
- **The system prompt was tuned by listening, not guessing.** In tests Aria read out bulleted lists and quoted prices in dollars for a UK hotel. The prompt now forces short spoken sentences, no lists, and prices in pounds.
- **The healthcheck had to match the container.** A curl-based healthcheck would fail forever on python slim images because curl is not installed, so the check pings /health with Python instead.
- **Errors are handled as conversation, not crashes.** Tools return structured JSON errors, like a booking clash, and Aria explains the problem and offers an alternative. I tested this by double-booking a room on purpose.
- **Docker had one real gotcha.** Running as a non-root user is easy until SQLite needs to write. The Dockerfile creates the data directory and hands ownership to the app user.

## What is mocked, honestly

The hotel itself (rooms, FAQs) is seeded demo data, and email confirmation is out of scope. Everything else is real: the MCP protocol, the agent loop, the database writes, the clash detection, and the voice pipeline.

## Production voice upgrade path

The voice layer is deliberately swappable, and half of the swap is already done: Aria's replies are synthesised with OpenAI neural TTS today. In production I would complete the picture with a telephony or streaming provider such as Twilio Media Streams or LiveKit, feeding call audio into a speech-to-text engine (Deepgram or Whisper) instead of the browser mic. The transcribed text would hit the same /chat endpoint the browser uses today. The agent loop, MCP tools, and database would not change by a single line, which is exactly why voice lives at the edge of this architecture.

## If this went to production next

Redis-backed sessions, authentication on the API, a telephony voice layer (Twilio or LiveKit), observability on tool calls, and container deployment. The service is stateless apart from SQLite, so it scales horizontally behind a load balancer.
