"""SQLite setup and seed data for The Grandview Hotel.

The MCP tools query and update this database. Kept as plain sqlite3 so
every query is visible and explainable.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "hotel.db"

ROOMS = [
    # (number, type, floor, view, price, quiet, accessible)
    (101, "Standard Double", 1, "courtyard", 95.0, 0, 1),
    (102, "Standard Twin", 1, "courtyard", 90.0, 0, 1),
    (204, "Standard Double", 2, "city", 110.0, 1, 0),
    (206, "Deluxe Double", 2, "city", 140.0, 1, 0),
    (301, "Deluxe Double", 3, "park", 155.0, 1, 0),
    (302, "Junior Suite", 3, "park", 210.0, 1, 0),
    (401, "Executive Suite", 4, "park", 320.0, 1, 0),
    (402, "Deluxe Twin", 4, "city", 150.0, 1, 0),
]

FAQS = [
    ("What time is check-in?", "Check-in opens at 3:00 PM. Early check-in from 1:00 PM is subject to availability."),
    ("What time is check-out?", "Check-out is at 11:00 AM. Late check-out until 1:00 PM can be requested for 25 pounds."),
    ("Is breakfast included?", "Breakfast is included with Deluxe and Suite bookings. For Standard rooms it is 12 pounds per person."),
    ("Do you have parking?", "Yes, secure underground parking is 18 pounds per night. Reserve in advance at busy periods."),
    ("Is the hotel pet friendly?", "Small pets under 10 kg are welcome in Standard rooms for a 20 pound cleaning fee per stay."),
    ("Do you have a gym or pool?", "The gym on floor 2 is open 6 AM to 10 PM. There is no pool."),
    ("Is Wi-Fi free?", "Yes, high-speed Wi-Fi is free throughout the hotel."),
    ("What is the cancellation policy?", "Free cancellation up to 48 hours before check-in. Inside 48 hours the first night is charged."),
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(reset: bool = False) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()
    if reset:
        cur.executescript("DROP TABLE IF EXISTS bookings; DROP TABLE IF EXISTS rooms; DROP TABLE IF EXISTS faqs;")

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            number INTEGER PRIMARY KEY,
            type TEXT NOT NULL,
            floor INTEGER NOT NULL,
            view TEXT NOT NULL,
            price REAL NOT NULL,
            quiet INTEGER NOT NULL,
            accessible INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT UNIQUE NOT NULL,
            guest_name TEXT NOT NULL,
            room_number INTEGER NOT NULL REFERENCES rooms(number),
            check_in TEXT NOT NULL,
            check_out TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmed'
        );
        CREATE TABLE IF NOT EXISTS faqs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL
        );
        """
    )

    if cur.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 0:
        cur.executemany("INSERT INTO rooms VALUES (?,?,?,?,?,?,?)", ROOMS)
    if cur.execute("SELECT COUNT(*) FROM faqs").fetchone()[0] == 0:
        cur.executemany("INSERT INTO faqs (question, answer) VALUES (?,?)", FAQS)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db(reset=True)
    print(f"Database created and seeded at {DB_PATH}")
