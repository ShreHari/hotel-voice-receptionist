"""FastAPI entrypoint: serves the voice UI and the /chat endpoint.

On startup it seeds the database, spawns the MCP server as a subprocess,
and connects to it once for the app's lifetime.
"""

import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()  # must run before the OpenAI client is created

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent import AriaAgent
from app.mcp_client import HotelMCPClient
from mcp_server.database import init_db

state: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    mcp = HotelMCPClient(command=sys.executable)
    tool_names = await mcp.connect()
    state["agent"] = AriaAgent(mcp)
    print(f"MCP server connected. Tools: {', '.join(tool_names)}")
    yield
    await mcp.close()


app = FastAPI(title="Grandview Hotel Voice Receptionist", lifespan=lifespan)


class ChatRequest(BaseModel):
    session_id: str
    message: str


class SpeakRequest(BaseModel):
    text: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(request: ChatRequest):
    return await state["agent"].chat(request.session_id, request.message)


@app.post("/speak")
async def speak(request: SpeakRequest):
    audio = await state["agent"].synthesize(request.text)
    return Response(content=audio, media_type="audio/mpeg")


# serve the voice UI (must be mounted last so /chat and /health win)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
