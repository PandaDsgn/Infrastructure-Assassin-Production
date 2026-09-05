import asyncio
import json
import os
import time

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

SEED_ROWS = [
    ("Alice Smith", "SaaS", "Figma Enterprise", 120, "2025-11-01", 45, False, False, "Active"),
    ("Bob Jones", "Server", "AWS EC2 Production", 450, "2024-03-15", 1, False, False, "Active"),
    ("Charlie Davis", "Software", "FreeVPN_Crack.exe", 0, "2026-05-20", 2, True, False, "Active"),
    ("Diana Prince", "SaaS", "GitLab Runner (v14.1)", 85, "2023-08-10", 5, False, True, "Active"),
    ("Evan Wright", "Cloud", "Datadog Test Environment", 850, "2026-01-12", 60, False, False, "Active"),
]

_pool: asyncpg.Pool | None = None
_listener_conn: asyncpg.Connection | None = None
_realtime_callback = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=DATABASE_URL)
    return _pool


async def query(text, params=None):
    pool = await get_pool()
    rows = await pool.fetch(text, *(params or []))
    return [dict(row) for row in rows]


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS resources (
                id SERIAL PRIMARY KEY,
                employee_name TEXT,
                resource_type TEXT,
                resource_name TEXT,
                monthly_cost INTEGER,
                install_date TEXT,
                days_since_last_login INTEGER,
                is_malicious BOOLEAN,
                needs_update BOOLEAN,
                status TEXT,
                pending_action_by TEXT DEFAULT NULL,
                pending_action_type TEXT DEFAULT NULL
            )
        """)
        await conn.execute(
            "ALTER TABLE resources ADD COLUMN IF NOT EXISTS pending_action_type TEXT DEFAULT NULL"
        )
        await conn.execute(
            "ALTER TABLE resources ADD COLUMN IF NOT EXISTS pending_log_id INTEGER DEFAULT NULL"
        )
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS request_log (
                id SERIAL PRIMARY KEY,
                resource_name TEXT,
                requester_uid TEXT,
                requester_name TEXT,
                action_type TEXT,
                status TEXT DEFAULT 'Pending',
                requested_at TIMESTAMPTZ DEFAULT NOW(),
                resolved_at TIMESTAMPTZ,
                resolved_by TEXT
            )
        """)

        count = await conn.fetchval("SELECT COUNT(*) FROM resources")
        if count == 0:
            print("Seeding production ledger database with initial enterprise data...")
            await conn.executemany(
                """INSERT INTO resources
                   (employee_name, resource_type, resource_name, monthly_cost, install_date,
                    days_since_last_login, is_malicious, needs_update, status)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                SEED_ROWS,
            )
            print("Database seeded successfully.")


def _on_notification(connection, pid, channel, payload):
    if channel != "realtime_events":
        return
    try:
        data = json.loads(payload)
        if _realtime_callback:
            _realtime_callback(data)
    except Exception as err:
        print("[REALTIME BUS] Failed to parse notification:", err)


async def _connect_listener():
    global _listener_conn
    conn = await asyncpg.connect(dsn=DATABASE_URL)
    await conn.add_listener("realtime_events", _on_notification)
    _listener_conn = conn
    print("📡 Realtime bus connected - LISTEN realtime_events")

    def _on_terminate(_connection):
        print("[REALTIME BUS] Listener connection dropped. Reconnecting in 2s...")
        asyncio.create_task(_reconnect_listener())

    conn.add_termination_listener(_on_terminate)


async def _reconnect_listener():
    await asyncio.sleep(2)
    await _connect_listener()


async def init_realtime_bus(on_event):
    global _realtime_callback
    _realtime_callback = on_event
    await _connect_listener()


async def publish_realtime_event(event_type, data=None):
    payload = json.dumps({"type": event_type, "data": data or {}, "timestamp": int(time.time() * 1000)})
    pool = await get_pool()
    await pool.execute("SELECT pg_notify('realtime_events', $1)", payload)
