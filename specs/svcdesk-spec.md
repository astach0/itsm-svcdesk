<!-- ai-generated: 100% - drafted with Gemini CLI from REQUIREMENTS.md and API.md -->
# Service Desk (svcdesk) Technical Specification

This document details the complete functional and technical specification for the `svcdesk` ticketing API. This specification incorporates the chosen system-design decisions (**C1 = wallclock**, **C2 = immutable**, and **C3 = vip**) and defines the expected behavior, data models, validation constraints, SLA calculation algorithms, state transitions, and environmental requirements.

---

## 1. Service Purpose and Scope

The `svcdesk` service is a lightweight IT service desk ticketing system designed for around 400 users in three offices. Its purpose is to transition ticket tracking from manual spreadsheets and emails into a structured HTTP API.

The service must:
- Expose a strict JSON-over-HTTP API on port `8080`.
- Automatically calculate incident priority from user-specified impact and urgency values.
- Implement specialized priority overrides for VIP reporters (**C3 = vip**).
- Maintain rigorous SLA Clocks for ticket acknowledgment and resolution targets.
- Use continuous **wall-clock** SLA tracking for critical **P1** tickets and **business-hours** SLA tracking for **P2, P3, and P4** tickets (**C1 = wallclock**).
- Restrict ticket state movement to a strict sequential state machine.
- Enforce that once a ticket is closed, it is completely **immutable** and cannot be reopened (**C2 = immutable**).
- Support a mockable test clock (`X-Test-Clock`) for deterministic verification and SLA auditing.

---

## 2. Technical Environment & Constraints

The service will be implemented as a **Python 3.13 FastAPI** application and deployed inside a Docker container.

- **Port:** Expose port `8080` inside the container.
- **Docker Compose:** The service must be defined in a `docker-compose.yml` (or `compose.yaml`) file under a service named `svcdesk`, configured to build directly from the repository.
- **No-Runtime-Network Requirement:** The containerized application must require **no network access** at runtime. All dependencies (such as FastAPI, Uvicorn, and any date/tz libraries) must be pre-installed during the image build phase (`docker build`).
- **No Host-Path Bind Mounts:** The Docker Compose configuration must not use any `type: bind` mounts or host-path mappings. State must be preserved using named volumes or tmpfs.
- **Persistence Requirement:** Ticket data must survive container restarts. The application should persist its state using a lightweight SQLite database file stored within a Docker named volume (e.g., in `/data/svcdesk.db` mapped to a persistent named volume).
- **Time Zone Database:** The Docker image must include the IANA time zone database containing `Europe/Warsaw` (for Debian slim images, this is typically pre-installed or available via `tzdata`).
- **Healthcheck Endpoint:** A dedicated `GET /health` endpoint must be online and return a `200 OK` response within 120 seconds of the container starting up.

---

## 3. Ignore & Ownership Rules (Request Sanitization)

To prevent data tampering and ensure system integrity, the API must enforce a strict separation between client-writable fields and server-owned fields.

### Server-Owned Fields
The following fields are strictly owned by the server. If they are sent in any client request (e.g., during `POST /tickets` or state transition calls), the server **must silently ignore them** and calculate/assign them internally:
- `id` (automatically generated unique string, UUID recommended).
- `priority` (calculated via the Priority Matrix and VIP rules).
- `state` (defaults to `"new"` on create, updated only via transition endpoints).
- `created_at`, `acknowledged_at`, `resolved_at`, `closed_at` (assigned by the server based on the request's logical "now").
- `sla` block (fully calculated by the server on ticket creation).

### Extra Fields
Any fields present in the client request JSON payload that are not explicitly defined in the Ticket model (unknown fields) must be **silently ignored** and must never trigger a validation error or be returned in the response.

---

## 4. Endpoints & HTTP Contracts

All requests and responses must use `application/json` as their `Content-Type`. Successful state-modifying actions must return `200 OK` (or `201 Created` for creation) with the full updated `Ticket` representation.

| Method | Path | Success Code | Description / Behavior |
|---|---|---|---|
| **GET** | `/health` | `200 OK` | Returns `{"status": "ok", "service": "svcdesk"}`. This endpoint may return extra fields but must include status and service. It does not read or require the test clock. |
| **POST** | `/tickets` | `201 Created` | Creates a new ticket. Calculates priority, computes the SLA due dates, sets state to `"new"`, and returns the created `Ticket` object. Returns `400` or `422` on validation failure. |
| **GET** | `/tickets` | `200 OK` | Lists all tickets. Supports optional query filters: `?state=<new\|acknowledged\|in_progress\|resolved\|closed>` and `?priority=<P1\|P2\|P3\|P4>`. Both filters are exact match and can be combined. Returns a JSON array of all matching `Ticket` objects in any order without pagination. |
| **GET** | `/tickets/{id}` | `200 OK` | Retrieves a single ticket by its unique identifier. Returns `404` if the ticket identifier is unknown. |
| **GET** | `/tickets/{id}/sla`| `200 OK` | Computes and returns the SLA status block for the ticket evaluated at the request's logical "now" (SLA target tracking). Returns `404` if unknown. |
| **POST** | `/tickets/{id}/ack` | `200 OK` | Moves ticket state from `"new"` to `"acknowledged"`. Sets `acknowledged_at` to logical "now". Returns `409` on invalid transition or `404` if unknown. |
| **POST** | `/tickets/{id}/start`| `200 OK` | Moves ticket state from `"acknowledged"` to `"in_progress"`. Returns `409` on invalid transition or `404` if unknown. |
| **POST**| `/tickets/{id}/resolve`| `200 OK` | Moves ticket state from `"in_progress"` to `"resolved"`. Sets `resolved_at` to logical "now". Returns `409` on invalid transition or `404` if unknown. |
| **POST**| `/tickets/{id}/close`| `200 OK` | Moves ticket state from `"resolved"` to `"closed"`. Sets `closed_at` to logical "now". Returns `409` on invalid transition or `404` if unknown. |
| **POST**| `/tickets/{id}/reopen`| `200 OK` | Moves ticket state from `"resolved"` back to `"in_progress"`. Clears `resolved_at` and `closed_at`. Under **C2 = immutable**, reopening from `"closed"` is strictly forbidden and returns `409`. Returns `409` if the 7-day reopen window has expired, or `404` if unknown. |
| **Any** | *Unknown Path* | `404 Not Found`| Any request to an undefined path or using an incorrect method on a known path must return `404` (or `405 Method Not Allowed`) with a JSON body carrying an error object. |

---

## 5. Detailed Data Models & Validation Rules

### The Ticket Schema

Each `Ticket` is represented by the following JSON structure:

```json
{
  "id": "string (opaque, unique, non-empty, UUID recommended)",
  "title": "string (1 to 200 characters)",
  "description": "string (0 to 4000 characters, default is empty string \"\")",
  "reporter": {
    "name": "string (1 to 100 characters)",
    "email": "string or null (optional, default is null)",
    "vip": "boolean (optional, default is false)"
  },
  "impact": "integer (1, 2, or 3)",
  "urgency": "integer (1, 2, or 3)",
  "priority": "string (\"P1\", \"P2\", \"P3\", or \"P4\")",
  "state": "string (\"new\", \"acknowledged\", \"in_progress\", \"resolved\", \"closed\")",
  "created_at": "string (RFC 3339 UTC instant, Z suffix)",
  "acknowledged_at": "string or null (RFC 3339 UTC instant, Z suffix, null until acknowledged)",
  "resolved_at": "string or null (RFC 3339 UTC instant, Z suffix, null until resolved)",
  "closed_at": "string or null (RFC 3339 UTC instant, Z suffix, null until closed)",
  "related_to": "string or null (optional ticket ID of a related earlier ticket, default is null)",
  "sla": {
    "ack_due_at": "string (RFC 3339 UTC instant, Z suffix)",
    "resolve_due_at": "string (RFC 3339 UTC instant, Z suffix)"
  }
}
```

### Validation Constraints

Any request that fails to satisfy the following constraints must be rejected with **HTTP 400 Bad Request** or **HTTP 422 Unprocessable Entity**. The response body must carry a JSON object with a top-level `"error"` key containing detailed context (e.g., `{"error": {"code": "validation", "message": "title is required"}}`).

1. **`title`:** Must be present, a string, and its length must be between 1 and 200 characters inclusive.
2. **`description`:** Optional. If present, must be a string up to 4000 characters. If missing, it defaults to `""`.
3. **`reporter`:** Must be a JSON object containing:
   - `name`: Required string, 1 to 100 characters inclusive.
   - `email`: Optional string or null. If omitted, defaults to `null`.
   - `vip`: Optional boolean. If omitted, defaults to `false`.
4. **`impact`:** Required integer. Must be exactly `1`, `2`, or `3`. Strings (such as `"high"` or `"1"`) or other integers are malformed and must be rejected.
5. **`urgency`:** Required integer. Must be exactly `1`, `2`, or `3`. Strings or other integers are malformed and must be rejected.
6. **`related_to`:** Optional string or null. (Note: The structural existence of the referenced ticket is not validated in Lab 1).

---

## 6. Priority Matrix and VIP Overrides (C3 = vip)

The service must compute a ticket's priority automatically upon creation.

### Base Priority Matrix
The initial priority is determined strictly by the combination of `impact` and `urgency`:

| Impact | Urgency 1 (Work Stopped) | Urgency 2 (Degraded) | Urgency 3 (Cosmetic) |
|:---|:---:|:---:|:---:|
| **1 (Whole Organisation)** | **P1** | **P2** | **P3** |
| **2 (Team)** | **P2** | **P3** | **P4** |
| **3 (One Person)** | **P3** | **P4** | **P4** |

### VIP Priority Promotion under C3 = vip
Once the base priority is calculated, the system applies the VIP override logic:
- If `reporter.vip` is `true`, the ticket priority **cannot be lower than P2**.
- Therefore, if the base priority from the matrix is **P3** or **P4**, it is automatically elevated to **P2**.
- If the base priority is already **P1** or **P2**, it remains unchanged.
- If `reporter.vip` is `false`, the base priority is used directly.

*Example:* A ticket with impact 3, urgency 3, and `reporter.vip = true` is computed as **P2** (elevated from the base P4).

---

## 7. SLA Target Clocks (C1 = wallclock)

SLA targets define the time limits within which a ticket must be acknowledged and resolved, measured from its creation time (`created_at`).

### Targets by Priority

| Priority | Acknowledge Within | Resolve Within |
|:---|:---:|:---:|
| **P1** | 15 minutes | 4 hours |
| **P2** | 1 hour | 8 hours |
| **P3** | 4 hours | 24 hours |
| **P4** | 8 hours | 72 hours |

### Clock Behaviors (Decision: C1 = wallclock)
Under the **C1 = wallclock** decision, the SLA tracking clocks are split:
1. **P1 Clocks (Wall-clock):** P1 SLA targets run on a continuous wall-clock.
   - The due instants are calculated simply as: `ack_due_at = created_at + 15 minutes` and `resolve_due_at = created_at + 4 hours`.
   - This operates 24/7/365, meaning P1 clocks never pause outside of business hours.
2. **P2, P3, and P4 Clocks (Business-hours):** These targets count only time elapsed within defined business hours.
   - Time outside business hours does not count toward the SLA limit.

### Business Hours Specification
- **Time Zone:** All business-hours calculations must be performed in the `Europe/Warsaw` timezone (fully DST-aware).
- **Weekly Window:** Monday to Friday, from **08:00:00** local time up to (but not including) **16:00:00** local time (represented as the half-open local interval `[08:00:00, 16:00:00)`).
- **Weekends:** Saturdays and Sundays are entirely outside business hours.
- **Holidays:** Polish public holidays are treated as normal business days (out of scope for calculation).

### Business-Hours SLA Calculation Algorithm
To compute a business-hours due instant for a target duration $D$ starting from a creation instant $T_{start}$:
1. Convert $T_{start}$ from UTC to `Europe/Warsaw` local time. Let this be $L$.
2. **Align to Business Hours:** If $L$ is outside a business window (i.e., it is a Saturday or Sunday, or it falls on a weekday before 08:00:00 or at/after 16:00:00):
   - Fast-forward $L$ to the next weekday opening time (**08:00:00** of the next Monday-to-Friday business day).
3. **Consume Duration:** While the remaining target duration $D$ is greater than the time left in the current day's business window (which is the duration from $L$ to `16:00:00` of that same day):
   - Subtract the time left in the current day's window from $D$.
   - Move $L$ to **08:00:00** of the next business day (skipping weekends).
4. **Final Allocation:** Once the remaining duration $D$ is less than or equal to the time left in the current day's business window:
   - Add the remaining $D$ to $L$. This is the local due time.
5. **Tie Rule:** If the duration $D$ is consumed exactly to the end of a business day's window, the due instant is exactly **16:00:00** of that local business day (rather than wrapping to 08:00:00 of the next).
6. Convert the final local due time back to UTC and format it with a `Z` suffix.

---

## 8. Exact SLA Test Vectors

Your implementation must compute these exact UTC instants for the SLA targets.

| ID | Priority | Created At (UTC) | Local Time (Warsaw) | Ack Due (UTC) | Resolve Due (UTC) | Clock Types / Notes |
|---|---|---|---|---|---|---|
| **T1** | P1 | `2026-10-14T10:00:00Z` | Wed 12:00 CEST | `2026-10-14T10:15:00Z` | `2026-10-14T14:00:00Z` | Wall-clock (P1). Since created inside business hours, identical to business clock. |
| **T2** | P3 | `2026-10-16T13:30:00Z` | Fri 15:30 CEST | `2026-10-19T09:30:00Z` | `2026-10-21T13:30:00Z` | Business. Ack (4h) consumes 30m on Fri, remaining 3h30m on Mon $\rightarrow$ Mon 09:30. Resolve (24h) consumes 30m on Fri, 8h on Mon, 8h on Tue, remaining 7h30m on Wed $\rightarrow$ Wed 15:30. |
| **T3** | P1 | `2026-10-16T15:00:00Z` | Fri 17:00 CEST | `2026-10-16T15:15:00Z` | `2026-10-16T19:00:00Z` | Wall-clock (P1 under C1=wallclock). continuous 15m/4h tracking regardless of weekend. |
| **T4** | P2 | `2026-10-17T10:00:00Z` | Sat 12:00 CEST | `2026-10-19T07:00:00Z` | `2026-10-19T14:00:00Z` | Business. Created on weekend, starts Mon 08:00 local (06:00Z). Ack (1h) due Mon 09:00 local (07:00Z). Resolve (8h) due Mon 16:00 local (14:00Z) $\rightarrow$ exact tie-rule. |
| **T5** | P4 | `2027-01-14T14:30:00Z` | Thu 15:30 CET | `2027-01-15T14:30:00Z` | `2027-01-27T14:30:00Z` | Business (Winter CET, UTC+1). Resolve (72h) consumes 30m on Thu, 40h over next 5 weekdays (Fri, Mon, Tue, Wed, Thu), remaining 31h30m over subsequent business days. |
| **T6** | P1 | `2027-01-15T15:50:00Z` | Fri 16:50 CET | `2027-01-15T16:05:00Z` | `2027-01-15T19:50:00Z` | Wall-clock (P1). continuous tracking. |
| **T7** | P2 | `2026-10-14T10:00:00Z` | Wed 12:00 CEST | `2026-10-14T11:00:00Z` | `2026-10-15T10:00:00Z` | Business. Resolve (8h) consumes 4h on Wed (up to 16:00 local), and remaining 4h on Thu (starting 08:00 local) $\rightarrow$ Thu 12:00 local (10:00Z). |
| **T8** | P3 | `2026-10-23T13:00:00Z` | Fri 15:00 CEST | `2026-10-26T10:00:00Z` | `2026-10-28T14:00:00Z` | Business. Spans DST end (Sunday Oct 25, clocks fall back). Resolve (24h) consumes 1h on Fri, 8h on Mon (after DST change), 8h on Tue, remaining 7h on Wed $\rightarrow$ Wed 15:00 CET = 14:00Z. |

---

## 9. SLA Breach & Pause Semantics (`GET /tickets/{id}/sla`)

The SLA status must be evaluated dynamically at the request's logical "now" (which is determined by the test clock header if present, or real time).

The endpoint returns:
```json
{
  "priority": "string (\"P1\" | \"P2\" | \"P3\" | \"P4\")",
  "ack_due_at": "string (RFC 3339 UTC instant)",
  "resolve_due_at": "string (RFC 3339 UTC instant)",
  "ack_breached": "boolean",
  "resolve_breached": "boolean",
  "paused": "boolean"
}
```

### Calculation Rules
1. **`ack_breached`:**
   - If the ticket has **not** been acknowledged (`acknowledged_at` is null), then `ack_breached` is `true` if `now > ack_due_at`, and `false` otherwise.
   - If the ticket **has** been acknowledged (`acknowledged_at` is not null), then `ack_breached` is `true` if `acknowledged_at > ack_due_at`, and `false` otherwise.
   - Reaching the due instant *exactly* (i.e. `now == ack_due_at` or `acknowledged_at == ack_due_at`) is **not** a breach.
2. **`resolve_breached`:**
   - If the ticket is currently **unresolved** (state is not `"resolved"` or `"closed"`), then `resolve_breached` is `true` if `now > resolve_due_at`, and `false` otherwise.
   - If the ticket **has** been resolved (`resolved_at` is not null), then `resolve_breached` is `true` if `resolved_at > resolve_due_at`, and `false` otherwise.
   - A reopened ticket is treated as **unresolved** again. Its `resolve_breached` is re-evaluated against the original `resolve_due_at`.
   - Reaching the due instant *exactly* is **not** a breach.
3. **`paused`:**
   - A ticket's SLA clock is paused if and only if **all** of the following conditions are met:
     1. The ticket is currently **open** (state is `"new"`, `"acknowledged"`, or `"in_progress"`; i.e., neither `"resolved"` nor `"closed"`).
     2. The ticket's SLA clock runs on the **business-hours** clock (i.e., it is a **P2, P3, or P4** ticket).
     3. The request's logical "now" falls **outside** of the `Europe/Warsaw` business hours window.
   - For **P1** tickets (which run on the wall-clock), `paused` is **always `false`**.
   - If the ticket is `"resolved"` or `"closed"`, `paused` is **always `false`**.

---

## 10. State Machine and Reopen Window

The service enforces a strict linear progression of states. No shortcuts (such as jumping from `new` directly to `in_progress` or `resolved`) are allowed.

```
 [new]
   │
   ▼ (POST /tickets/{id}/ack)
 [acknowledged]
   │
   ▼ (POST /tickets/{id}/start)
 [in_progress]
   │
   ▼ (POST /tickets/{id}/resolve)
 [resolved]
   │
   ├──► (POST /tickets/{id}/close) ──► [closed] (IMMUTABLE - NO REOPENING)
   │
   └──► (POST /tickets/{id}/reopen) ──► [in_progress] (Within 7-day window)
```

### Allowed Transitions and Side Effects

1. **Acknowledge (`POST /tickets/{id}/ack`):**
   - Allowed from: `"new"`.
   - Transition to: `"acknowledged"`.
   - Side Effect: Sets `acknowledged_at` to logical "now".
2. **Start Work (`POST /tickets/{id}/start`):**
   - Allowed from: `"acknowledged"`.
   - Transition to: `"in_progress"`.
   - Side Effect: None.
3. **Resolve (`POST /tickets/{id}/resolve`):**
   - Allowed from: `"in_progress"`.
   - Transition to: `"resolved"`.
   - Side Effect: Sets `resolved_at` to logical "now".
4. **Close (`POST /tickets/{id}/close`):**
   - Allowed from: `"resolved"`.
   - Transition to: `"closed"`.
   - Side Effect: Sets `closed_at` to logical "now".
5. **Reopen (`POST /tickets/{id}/reopen`):**
   - Allowed from: `"resolved"` (within the 7-day window).
   - Transition to: `"in_progress"`.
   - Side Effect: Clears `resolved_at` and `closed_at` (sets both to `null`).
   - Under **C2 = immutable**, reopening from `"closed"` is strictly **forbidden**. Attempting to reopen a closed ticket must immediately return `409 Conflict`.
   - **The Reopen Window:** Reopening from `"resolved"` is only allowed if `now <= resolved_at + 7 days`. If `now > resolved_at + 7 days`, the request is refused with `409 Conflict` (reopen window expired).
   - Reopening **does not** reset or extend the ticket's original SLA targets.

### Error Handling for Invalid Transitions
Any transition request that violates the state machine flow (including action on an invalid starting state) must be rejected with **HTTP 409 Conflict** and return a JSON error body containing a top-level `"error"` block, e.g., `{"error": {"code": "invalid_transition", "message": "..."}}`.

---

## 11. Test Clock Behavior (`X-Test-Clock`)

For deterministic automated testing and SLA verification, the service supports a mockable logical clock.

- **Trigger:** Enabled only when the container environment variable `SVCDESK_TEST_CLOCK` is set to `"1"` or `"true"`.
- **Header:** If enabled, any incoming HTTP request may carry an `X-Test-Clock` header containing an RFC 3339 timestamp with offset (e.g., `2026-10-14T10:00:00Z`).
- **Parsing:** If the header is present but does not parse as a valid RFC 3339 timestamp with timezone offset, the service must return **HTTP 400** or **HTTP 422**.
- **Usage:**
  - The value of `X-Test-Clock` represents the logical `"now"` (the current instant) for the scope of **that request only**.
  - Any server-generated timestamps for actions executed in that request (e.g., `created_at`, `acknowledged_at`, `resolved_at`, `closed_at`) must be set to this logical `"now"`.
  - Calculations for SLA due times, SLA breaches, paused states, and the 7-day reopen window must use this logical `"now"` as the current reference time.
- **Clock Isolation:**
  - The mock clock is strictly per-request and stateless.
  - The service **does not maintain** any global test clock state and **never compares** the clock of one incoming request with the clock of another.
  - The service **never enforces monotonic time** across requests and **never rejects** an action because its request-provided clock is earlier than a previously stored timestamp in the database (e.g., if a ticket has `created_at` at 12:00, and a subsequent `/ack` request provides `X-Test-Clock` at 10:00, the action is successfully processed, and `acknowledged_at` is written as 10:00).
- **Default Behavior:** If `SVCDESK_TEST_CLOCK` is disabled, unset, or set to `"0"`, the `X-Test-Clock` header is silently ignored, and the service uses the actual system UTC time.

---

## 12. Error Response Requirements

Whenever an HTTP request fails (400, 422, 404, 409), the response body must return a JSON object with a top-level `"error"` key. This object should contain informative keys such as `"code"` and `"message"`.

Examples of expected error responses:

- **Validation Failure (400/422):**
  ```json
  {
    "error": {
      "code": "validation",
      "message": "title is required and must be 1-200 characters"
    }
  }
  ```

- **Conflict / Invalid Transition (409):**
  ```json
  {
    "error": {
      "code": "invalid_transition",
      "message": "Cannot start a ticket in state 'new'. Must be 'acknowledged' first."
    }
  }
  ```

- **Ticket Not Found (404):**
  ```json
  {
    "error": {
      "code": "not_found",
      "message": "Ticket with ID 'abc-123' does not exist"
    }
  }
  ```

---

## 13. Mapping Specifications to Core Checks

Below is a reference guide mapping specific requirements and behaviors to their corresponding validation checks in `CHECKS.md`:

| Requirement | System Behavior | Covered by Check |
|---|---|---|
| **R-02 / R-24** | Health endpoint returns `"status": "ok"` within 120s | `L1-CORE-1.04`, `L1-CORE-2.01` |
| **R-21** | Logical test clock is honored via `X-Test-Clock` | `L1-CORE-2.03` |
| **R-21** | Malformed clock input is rejected with 400 or 422 | `L1-CORE-2.04` |
| **R-03 / R-20**| Basic ticket validation rules and output format | `L1-CORE-2.05`, `L1-CORE-2.16`, `L1-CORE-2.17`, `L1-CORE-2.18`, `L1-CORE-2.19` |
| **R-18** | Distinct, server-allocated unique IDs | `L1-CORE-2.06` |
| **R-04** | Base priority matrix calculations | `L1-CORE-2.07` through `L1-CORE-2.15` |
| **R-19** | Exact-match filters for listing tickets | `L1-CORE-2.22` (state), `L1-CORE-2.23` (priority) |
| **R-07** | Acknowledge state transition and timestamping | `L1-CORE-2.24` |
| **R-08** | Enforces chronological state flow (prevents out-of-order) | `L1-CORE-2.25` (double ack), `L1-CORE-2.26` (direct start), `L1-CORE-2.29` (direct resolve), `L1-CORE-2.31` (direct close), `L1-CORE-2.49` (resolve on ack without start) |
| **R-10 / R-11**| Reopens resolved tickets inside the 7-day window, rejects after | `L1-CORE-2.32` (within 6 days), `L1-CORE-2.33` (after 7 days + 1s) |
| **C2 = immutable**| Cannot reopen closed tickets; immutability enforced | `L1-CORE-2.35` (reopening closed ticket fails with 409) |
| **C1 = wallclock**| SLA vector T1 (P1 created inside business hours) | `L1-CORE-2.36` |
| **C1 = wallclock**| SLA vector T7 (P2 business hours crosses closing) | `L1-CORE-2.37` |
| **C1 = wallclock**| SLA vector T2 (P3 business hours Friday afternoon) | `L1-CORE-2.38` |
| **C1 = wallclock**| SLA vector T4 (P2 business hours Saturday tie rule) | `L1-CORE-2.39` |
| **C1 = wallclock**| SLA vector T5 (P4 business hours January CET) | `L1-CORE-2.40` |
| **C1 = wallclock**| SLA vector T3 (P1 wall-clock outside business hours) | `L1-CORE-2.41` (observes `wallclock` behavior) |
| **R-15 / R-16**| SLA breach evaluations | `L1-CORE-2.42` (breached after due), `L1-CORE-2.43` (not breached before due), `L1-CORE-2.44` (acknowledged in time is not breached) |
| **R-16** | SLA pause mechanics (paused outside business hours) | `L1-CORE-2.45` |
| **C3 = vip** | VIP priority promotions (P3/P4 raised to P2) | `L1-CORE-2.46` (observes `vip` behavior) |
| **C3 = vip** | VIP P1 tickets remain P1 | `L1-CORE-2.47` |
| **R-20** | Client-submitted priorities are silently ignored | `L1-CORE-2.48` |
