"""Aria, the agent.

A hand-written agentic loop, no framework: the model reasons, requests
MCP tools when it needs facts or actions, the results are fed back, and
it repeats until it can answer the guest. Kept deliberately readable.
"""

import json
import os
from datetime import date

from openai import AsyncOpenAI

from app.mcp_client import HotelMCPClient

MAX_TOOL_ROUNDS = 6
HISTORY_LIMIT = 30  # keep the last N messages per session as short-term memory

SYSTEM_PROMPT = f"""You are Aria, the warm and efficient AI voice receptionist at The Grandview Hotel.

Today's date is {date.today().isoformat()}.

How you work:
- Your replies are spoken aloud, so keep them short, natural, and conversational. One to three sentences. No markdown, no bullet points, no emojis, never read out a list. When several rooms match, mention only the best two or three in flowing speech.
- All prices are in British pounds. Say "pounds", never dollars.
- Never invent hotel facts. For availability, prices, bookings, cancellations, or hotel policies, always use your tools.
- When a guest states preferences (budget, view, quiet, accessible, floor), use the search_rooms tool with those filters and recommend the best match.
- Before creating a booking, confirm the guest's full name, the room, and the dates back to them, then book.
- After booking, read the reference clearly, for example "your reference is G V dash 7 1 9 W F P".
- If a tool returns an error, explain it simply and offer an alternative.
- If asked something outside hotel matters, politely steer back to how you can help with their stay.
"""


class AriaAgent:
    def __init__(self, mcp: HotelMCPClient):
        self.client = AsyncOpenAI()
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.mcp = mcp
        self.sessions: dict[str, list[dict]] = {}

    def _history(self, session_id: str) -> list[dict]:
        if session_id not in self.sessions:
            self.sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
        return self.sessions[session_id]

    def _trim(self, messages: list[dict]) -> None:
        # keep the system prompt plus the most recent turns
        if len(messages) > HISTORY_LIMIT:
            del messages[1:len(messages) - HISTORY_LIMIT + 1]

    async def chat(self, session_id: str, user_message: str) -> dict:
        messages = self._history(session_id)
        messages.append({"role": "user", "content": user_message})
        tools_used: list[str] = []

        for _ in range(MAX_TOOL_ROUNDS):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.mcp.openai_tools,
                temperature=0.7,
            )
            msg = response.choices[0].message

            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
                })
                for tc in msg.tool_calls:
                    arguments = json.loads(tc.function.arguments or "{}")
                    result = await self.mcp.call_tool(tc.function.name, arguments)
                    tools_used.append(tc.function.name)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                continue  # let the model read the tool results and go again

            messages.append({"role": "assistant", "content": msg.content})
            self._trim(messages)
            return {"reply": msg.content, "tools_used": tools_used}

        return {
            "reply": "Sorry, I had trouble completing that. Could you say it again slightly differently?",
            "tools_used": tools_used,
        }
