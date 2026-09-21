# ai-generated: 100% - Handcrafted by Gemini CLI implementation
from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictInt
from typing import Optional, List
from datetime import datetime, timezone, timedelta, time
from zoneinfo import ZoneInfo
import sqlite3
import os
import uuid
from contextlib import asynccontextmanager

# Config
DB_PATH = os.environ.get("SVCDESK_DB", "svcdesk.db")

# Ensure parent directory of DB_PATH exists
db_dir = os.path.dirname(DB_PATH)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

# Timezone
warsaw_tz = ZoneInfo("Europe/Warsaw")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        reporter_name TEXT NOT NULL,
        reporter_email TEXT,
        reporter_vip INTEGER NOT NULL,
        impact INTEGER NOT NULL,
        urgency INTEGER NOT NULL,
        priority TEXT NOT NULL,
        state TEXT NOT NULL,
        created_at TEXT NOT NULL,
        acknowledged_at TEXT,
        resolved_at TEXT,
        closed_at TEXT,
        related_to TEXT,
        ack_due_at TEXT NOT NULL,
        resolve_due_at TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

# DB Dependency
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Request time dependency (test clock)
def get_request_time(x_test_clock: Optional[str] = Header(None, alias="X-Test-Clock")) -> datetime:
    test_clock_enabled = os.environ.get("SVCDESK_TEST_CLOCK", "").lower() in ("1", "true")
    if test_clock_enabled and x_test_clock:
        try:
            val = x_test_clock
            if val.endswith('Z'):
                val = val[:-1] + '+00:00'
            dt = datetime.fromisoformat(val)
            if dt.tzinfo is None:
                raise ValueError("Naive timestamp is malformed")
            return dt.astimezone(timezone.utc)
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail={"error": {"code": "validation", "message": f"Malformed X-Test-Clock header: {e}"}}
            )
    return datetime.now(timezone.utc)

# Helpers for Warsaw business hours calculation
def is_business_day(dt: datetime) -> bool:
    return dt.weekday() < 5

def align_to_business_hours(dt: datetime) -> datetime:
    # dt is in Warsaw local time
    if not is_business_day(dt):
        curr = dt + timedelta(days=1)
        while not is_business_day(curr):
            curr += timedelta(days=1)
        return curr.replace(hour=8, minute=0, second=0, microsecond=0)
    else:
        t = dt.time()
        if t < time(8, 0, 0):
            return dt.replace(hour=8, minute=0, second=0, microsecond=0)
        elif t >= time(16, 0, 0):
            curr = dt + timedelta(days=1)
            while not is_business_day(curr):
                curr += timedelta(days=1)
            return curr.replace(hour=8, minute=0, second=0, microsecond=0)
    return dt

def add_business_seconds(start_dt: datetime, seconds_to_add: int) -> datetime:
    # Convert to Warsaw local time
    local_dt = start_dt.astimezone(warsaw_tz)
    remaining = seconds_to_add

    while remaining > 0:
        local_dt = align_to_business_hours(local_dt)
        window_end = local_dt.replace(hour=16, minute=0, second=0, microsecond=0)
        available = int((window_end - local_dt).total_seconds())

        if remaining <= available:
            local_dt += timedelta(seconds=remaining)
            remaining = 0
        else:
            remaining -= available
            local_dt = window_end

    return local_dt

def is_outside_business_hours(dt: datetime) -> bool:
    local_dt = dt.astimezone(warsaw_tz)
    if not is_business_day(local_dt):
        return True
    t = local_dt.time()
    return t < time(8, 0, 0) or t >= time(16, 0, 0)

# Format UTC times for DB / JSON
def format_instant(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

# Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "error", "message": str(exc.detail)}}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    messages = []
    for err in errors:
        loc = " -> ".join(str(x) for x in err.get("loc", []))
        msg = err.get("msg", "invalid value")
        messages.append(f"{loc}: {msg}")
    full_msg = "; ".join(messages)
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation", "message": full_msg}}
    )

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=404,
        content={"error": {"code": "not_found", "message": "Resource not found"}}
    )

# Priority calculation
def get_base_priority(impact: int, urgency: int) -> str:
    if impact == 1:
        if urgency == 1: return "P1"
        if urgency == 2: return "P2"
        if urgency == 3: return "P3"
    elif impact == 2:
        if urgency == 1: return "P2"
        if urgency == 2: return "P3"
        if urgency == 3: return "P4"
    elif impact == 3:
        if urgency == 1: return "P3"
        if urgency == 2: return "P4"
        if urgency == 3: return "P4"
    raise ValueError("Invalid impact or urgency value")

def calculate_priority(impact: int, urgency: int, is_vip: bool) -> str:
    base = get_base_priority(impact, urgency)
    if is_vip and base in ("P3", "P4"):
        return "P2"
    return base

# Pydantic Request Models
class ReporterModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: Optional[str] = Field(default=None)
    vip: bool = Field(default=False)

class TicketCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default="")
    reporter: ReporterModel
    impact: StrictInt = Field(..., ge=1, le=3)
    urgency: StrictInt = Field(..., ge=1, le=3)
    related_to: Optional[str] = Field(default=None)

# Database Mapper
def row_to_ticket_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"] if row["description"] is not None else "",
        "reporter": {
            "name": row["reporter_name"],
            "email": row["reporter_email"],
            "vip": bool(row["reporter_vip"])
        },
        "impact": row["impact"],
        "urgency": row["urgency"],
        "priority": row["priority"],
        "state": row["state"],
        "created_at": row["created_at"],
        "acknowledged_at": row["acknowledged_at"],
        "resolved_at": row["resolved_at"],
        "closed_at": row["closed_at"],
        "related_to": row["related_to"],
        "sla": {
            "ack_due_at": row["ack_due_at"],
            "resolve_due_at": row["resolve_due_at"]
        }
    }

# API Endpoints
@app.get("/health")
async def health():
    return {"status": "ok", "service": "svcdesk"}

@app.post("/tickets", status_code=201)
async def create_ticket(
    ticket_in: TicketCreate,
    now: datetime = Depends(get_request_time),
    db: sqlite3.Connection = Depends(get_db)
):
    ticket_id = str(uuid.uuid4())
    priority = calculate_priority(ticket_in.impact, ticket_in.urgency, ticket_in.reporter.vip)

    # SLA calculations
    if priority == "P1":
        # Wall-clock
        ack_due = now + timedelta(minutes=15)
        resolve_due = now + timedelta(hours=4)
    elif priority == "P2":
        ack_due = add_business_seconds(now, 1 * 3600)
        resolve_due = add_business_seconds(now, 8 * 3600)
    elif priority == "P3":
        ack_due = add_business_seconds(now, 4 * 3600)
        resolve_due = add_business_seconds(now, 24 * 3600)
    elif priority == "P4":
        ack_due = add_business_seconds(now, 8 * 3600)
        resolve_due = add_business_seconds(now, 72 * 3600)
    else:
        # Fallback safety
        ack_due = now
        resolve_due = now

    created_at_str = format_instant(now)
    ack_due_str = format_instant(ack_due)
    resolve_due_str = format_instant(resolve_due)

    cursor = db.cursor()
    cursor.execute("""
    INSERT INTO tickets (
        id, title, description, reporter_name, reporter_email, reporter_vip,
        impact, urgency, priority, state, created_at, acknowledged_at,
        resolved_at, closed_at, related_to, ack_due_at, resolve_due_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticket_id, ticket_in.title, ticket_in.description or "",
        ticket_in.reporter.name, ticket_in.reporter.email, 1 if ticket_in.reporter.vip else 0,
        ticket_in.impact, ticket_in.urgency, priority, "new", created_at_str,
        None, None, None, ticket_in.related_to, ack_due_str, resolve_due_str
    ))
    db.commit()

    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    row = cursor.fetchone()
    return row_to_ticket_dict(row)

@app.get("/tickets")
async def list_tickets(
    state: Optional[str] = None,
    priority: Optional[str] = None,
    db: sqlite3.Connection = Depends(get_db)
):
    query = "SELECT * FROM tickets"
    params = []
    conditions = []
    if state is not None:
        conditions.append("state = ?")
        params.append(state)
    if priority is not None:
        conditions.append("priority = ?")
        params.append(priority)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    cursor = db.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    return [row_to_ticket_dict(row) for row in rows]

@app.get("/tickets/{id}")
async def get_ticket(id: str, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": f"Ticket with ID {id} not found"}}
        )
    return row_to_ticket_dict(row)

@app.get("/tickets/{id}/sla")
async def get_ticket_sla(
    id: str,
    now: datetime = Depends(get_request_time),
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": f"Ticket with ID {id} not found"}}
        )

    priority = row["priority"]
    state = row["state"]

    def parse_db_time(t_str: str) -> Optional[datetime]:
        if not t_str:
            return None
        val = t_str
        if val.endswith('Z'):
            val = val[:-1] + '+00:00'
        return datetime.fromisoformat(val).astimezone(timezone.utc)

    ack_due_at = parse_db_time(row["ack_due_at"])
    resolve_due_at = parse_db_time(row["resolve_due_at"])
    acknowledged_at = parse_db_time(row["acknowledged_at"])
    resolved_at = parse_db_time(row["resolved_at"])

    # Ack breach
    if acknowledged_at is None:
        ack_breached = now > ack_due_at
    else:
        ack_breached = acknowledged_at > ack_due_at

    # Resolve breach
    if resolved_at is None:
        resolve_breached = now > resolve_due_at
    else:
        resolve_breached = resolved_at > resolve_due_at

    # Paused
    paused = False
    if state in ("new", "acknowledged", "in_progress") and priority in ("P2", "P3", "P4"):
        paused = is_outside_business_hours(now)

    return {
        "priority": priority,
        "ack_due_at": row["ack_due_at"],
        "resolve_due_at": row["resolve_due_at"],
        "ack_breached": ack_breached,
        "resolve_breached": resolve_breached,
        "paused": paused
    }

@app.post("/tickets/{id}/ack")
async def ack_ticket(
    id: str,
    now: datetime = Depends(get_request_time),
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": f"Ticket with ID {id} not found"}}
        )

    if row["state"] != "new":
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "invalid_transition", "message": f"Cannot acknowledge ticket in state {row['state']}"}}
        )

    now_str = format_instant(now)
    cursor.execute("""
    UPDATE tickets
    SET state = 'acknowledged', acknowledged_at = ?
    WHERE id = ?
    """, (now_str, id))
    db.commit()

    cursor.execute("SELECT * FROM tickets WHERE id = ?", (id,))
    return row_to_ticket_dict(cursor.fetchone())

@app.post("/tickets/{id}/start")
async def start_ticket(
    id: str,
    now: datetime = Depends(get_request_time),
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": f"Ticket with ID {id} not found"}}
        )

    if row["state"] != "acknowledged":
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "invalid_transition", "message": f"Cannot start ticket in state {row['state']}"}}
        )

    cursor.execute("""
    UPDATE tickets
    SET state = 'in_progress'
    WHERE id = ?
    """, (id,))
    db.commit()

    cursor.execute("SELECT * FROM tickets WHERE id = ?", (id,))
    return row_to_ticket_dict(cursor.fetchone())

@app.post("/tickets/{id}/resolve")
async def resolve_ticket(
    id: str,
    now: datetime = Depends(get_request_time),
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": f"Ticket with ID {id} not found"}}
        )

    if row["state"] != "in_progress":
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "invalid_transition", "message": f"Cannot resolve ticket in state {row['state']}"}}
        )

    now_str = format_instant(now)
    cursor.execute("""
    UPDATE tickets
    SET state = 'resolved', resolved_at = ?
    WHERE id = ?
    """, (now_str, id))
    db.commit()

    cursor.execute("SELECT * FROM tickets WHERE id = ?", (id,))
    return row_to_ticket_dict(cursor.fetchone())

@app.post("/tickets/{id}/close")
async def close_ticket(
    id: str,
    now: datetime = Depends(get_request_time),
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": f"Ticket with ID {id} not found"}}
        )

    if row["state"] != "resolved":
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "invalid_transition", "message": f"Cannot close ticket in state {row['state']}"}}
        )

    now_str = format_instant(now)
    cursor.execute("""
    UPDATE tickets
    SET state = 'closed', closed_at = ?
    WHERE id = ?
    """, (now_str, id))
    db.commit()

    cursor.execute("SELECT * FROM tickets WHERE id = ?", (id,))
    return row_to_ticket_dict(cursor.fetchone())

@app.post("/tickets/{id}/reopen")
async def reopen_ticket(
    id: str,
    now: datetime = Depends(get_request_time),
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": f"Ticket with ID {id} not found"}}
        )

    state = row["state"]

    # Decision C2 = immutable: reopen from closed is never allowed
    if state == "closed":
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "invalid_transition", "message": "Closed tickets are immutable and cannot be reopened"}}
        )

    if state != "resolved":
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "invalid_transition", "message": f"Cannot reopen ticket in state {state}"}}
        )

    resolved_at_str = row["resolved_at"]
    if not resolved_at_str:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "invalid_transition", "message": "Ticket is resolved but resolved_at is missing"}}
        )

    val = resolved_at_str
    if val.endswith('Z'):
        val = val[:-1] + '+00:00'
    resolved_at = datetime.fromisoformat(val).astimezone(timezone.utc)

    limit = resolved_at + timedelta(days=7)
    if now > limit:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "reopen_window_expired", "message": "Reopen window of 7 days has expired"}}
        )

    cursor.execute("""
    UPDATE tickets
    SET state = 'in_progress', resolved_at = NULL, closed_at = NULL
    WHERE id = ?
    """, (id,))
    db.commit()

    cursor.execute("SELECT * FROM tickets WHERE id = ?", (id,))
    return row_to_ticket_dict(cursor.fetchone())
