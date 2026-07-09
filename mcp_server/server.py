"""MCP server for The Grandview Hotel.

Exposes hotel operations as Model Context Protocol tools over stdio.
The agent process connects to this server as an MCP client, lists the
tools, and calls them when the LLM asks for an external action.

Run standalone for a quick smoke test:  python -m mcp_server.server
"""

import json
import random
import string
from datetime import date

from mcp.server.fastmcp import FastMCP

from mcp_server.database import get_connection, init_db

mcp = FastMCP("grandview-hotel")


def _new_reference() -> str:
    return "GV-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


@mcp.tool()
def check_availability(check_in: str, check_out: str) -> str:
    """List rooms free between check_in and check_out (dates as YYYY-MM-DD)."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT * FROM rooms WHERE number NOT IN (
            SELECT room_number FROM bookings
            WHERE status = 'confirmed'
              AND check_in < :out AND check_out > :in
        ) ORDER BY price
        """,
        {"in": check_in, "out": check_out},
    ).fetchall()
    conn.close()
    rooms = [dict(r) for r in rows]
    return json.dumps({"available_rooms": rooms, "count": len(rooms)})


@mcp.tool()
def search_rooms(max_price: float = 10000.0, view: str = "", quiet_only: bool = False,
                 accessible_only: bool = False, min_floor: int = 0) -> str:
    """Preference search: filter rooms by budget, view (city/park/courtyard), quietness, accessibility, floor."""
    query = "SELECT * FROM rooms WHERE price <= ?"
    params: list = [max_price]
    if view:
        query += " AND view = ?"
        params.append(view.lower())
    if quiet_only:
        query += " AND quiet = 1"
    if accessible_only:
        query += " AND accessible = 1"
    if min_floor:
        query += " AND floor >= ?"
        params.append(min_floor)
    query += " ORDER BY price"

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    matches = [dict(r) for r in rows]
    return json.dumps({"matching_rooms": matches, "count": len(matches)})


@mcp.tool()
def create_booking(guest_name: str, room_number: int, check_in: str, check_out: str) -> str:
    """Book a room for a guest. Dates as YYYY-MM-DD. Returns a booking reference."""
    conn = get_connection()
    room = conn.execute("SELECT * FROM rooms WHERE number = ?", (room_number,)).fetchone()
    if not room:
        conn.close()
        return json.dumps({"error": f"Room {room_number} does not exist."})

    clash = conn.execute(
        """
        SELECT reference FROM bookings
        WHERE room_number = ? AND status = 'confirmed'
          AND check_in < ? AND check_out > ?
        """,
        (room_number, check_out, check_in),
    ).fetchone()
    if clash:
        conn.close()
        return json.dumps({"error": f"Room {room_number} is already booked for those dates."})

    reference = _new_reference()
    conn.execute(
        "INSERT INTO bookings (reference, guest_name, room_number, check_in, check_out) VALUES (?,?,?,?,?)",
        (reference, guest_name, room_number, check_in, check_out),
    )
    conn.commit()
    conn.close()
    nights = max((date.fromisoformat(check_out) - date.fromisoformat(check_in)).days, 1)
    return json.dumps({
        "confirmed": True,
        "reference": reference,
        "guest_name": guest_name,
        "room_number": room_number,
        "room_type": room["type"],
        "check_in": check_in,
        "check_out": check_out,
        "total_price": round(nights * room["price"], 2),
    })


@mcp.tool()
def cancel_booking(reference: str) -> str:
    """Cancel an existing booking by its reference (format GV-XXXXXX)."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM bookings WHERE reference = ?", (reference.upper(),)).fetchone()
    if not row:
        conn.close()
        return json.dumps({"error": f"No booking found with reference {reference}."})
    if row["status"] == "cancelled":
        conn.close()
        return json.dumps({"error": f"Booking {reference} is already cancelled."})

    conn.execute("UPDATE bookings SET status = 'cancelled' WHERE reference = ?", (reference.upper(),))
    conn.commit()
    conn.close()
    return json.dumps({"cancelled": True, "reference": reference.upper(),
                       "note": "Free cancellation up to 48 hours before check-in."})


@mcp.tool()
def faq_search(query: str) -> str:
    """Search hotel FAQs (check-in times, breakfast, parking, pets, gym, Wi-Fi, cancellation policy)."""
    words = [w for w in query.lower().split() if len(w) > 2]
    conn = get_connection()
    rows = conn.execute("SELECT question, answer FROM faqs").fetchall()
    conn.close()

    scored = []
    for row in rows:
        text = (row["question"] + " " + row["answer"]).lower()
        score = sum(1 for w in words if w in text)
        if score:
            scored.append((score, dict(row)))
    scored.sort(key=lambda item: item[0], reverse=True)
    top = [entry for _, entry in scored[:2]]
    if not top:
        return json.dumps({"answer": None, "note": "No FAQ matched. Offer to connect the guest to the front desk."})
    return json.dumps({"results": top})


if __name__ == "__main__":
    init_db()
    mcp.run()
