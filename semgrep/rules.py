# ai-generated: 100% - Claude Code (Opus 5.5) wrote the test cases for semgrep/rules.yml (CI-SPEC.md P-31)
import sqlite3
from contextlib import closing

DB_PATH = "svcdesk.db"


def list_by_state(cursor, state):
    # ok: svcdesk-sql-query-not-literal
    cursor.execute("SELECT * FROM tickets WHERE state = ?", (state,))
    # ok: svcdesk-sql-query-not-literal
    cursor.execute("""
    SELECT * FROM tickets
    WHERE state = ?
    """, (state,))
    # ok: svcdesk-sql-query-not-literal
    cursor.executemany("INSERT INTO ticket_events (ticket_id) VALUES (?)", [("a",), ("b",)])
    return cursor.fetchall()


def list_filtered(cursor, state, priority):
    query = "SELECT * FROM tickets"
    conditions = []
    params = []
    if state is not None:
        conditions.append("state = ?")
        params.append(state)
    if priority is not None:
        conditions.append("priority = ?")
        params.append(priority)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    # ruleid: svcdesk-sql-query-not-literal
    cursor.execute(query, params)
    return cursor.fetchall()


def find_by_title(cursor, title):
    # ruleid: svcdesk-sql-query-not-literal
    cursor.execute(f"SELECT * FROM tickets WHERE title = '{title}'")
    # ruleid: svcdesk-sql-query-not-literal
    cursor.execute("SELECT * FROM tickets WHERE title = '" + title + "'")
    # ruleid: svcdesk-sql-query-not-literal
    cursor.executescript("DELETE FROM tickets WHERE id = '%s'" % title)
    return cursor.fetchall()


def init_db_leaky():
    # ruleid: svcdesk-sqlite-connection-not-closed-in-finally
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()


def get_db():
    # ok: svcdesk-sqlite-connection-not-closed-in-finally
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db_closed():
    # ok: svcdesk-sqlite-connection-not-closed-in-finally
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY)")
        conn.commit()
    finally:
        conn.close()


def init_db_with():
    # ok: svcdesk-sqlite-connection-not-closed-in-finally
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY)")
