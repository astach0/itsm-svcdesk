<!-- ai-generated: 100% - Written by Gemini CLI describing how requirements are fulfilled by the code -->

# Converge Report

This document reports on how the `svcdesk` implementation satisfies the project requirements.

## Mapping of Requirements

Our service desk implementation is fully aligned with the requirements defined in `REQUIREMENTS.md`. Specifically:

1. **R-02 (Health Monitoring)**: The `GET /health` endpoint is implemented as a simple, high-availability handler returning `{"status": "ok", "service": "svcdesk"}`. It requires no database interaction or test clock calculations, serving as a reliable uptime indicator for docker orchestration.

2. **R-07 (State Machine)**: The application implements a linear sequence of state changes from `new` to `acknowledged`, `in_progress`, `resolved`, and `closed` (and `in_progress` again on reopening from resolved). Every transition has a dedicated HTTP endpoint (`POST /tickets/{id}/ack`, `POST /tickets/{id}/start`, `POST /tickets/{id}/resolve`, `POST /tickets/{id}/close`, and `POST /tickets/{id}/reopen`), ensuring complete historical consistency.

3. **R-13 (Business Hours Clock)**: For priorities P2, P3, and P4, our SLA calculations utilize a DST-aware business-hours clock mapped to the `Europe/Warsaw` time zone. Time outside the `[08:00:00, 16:00:00)` half-open local interval on weekdays, as well as weekends (Saturdays and Sundays), is completely paused and excluded from elapsed targets.

4. **R-14 (Wall-Clock for P1)**: In accordance with our decision C1, P1 tickets represent critical incidents and bypass the business hours pauses. P1 tickets compute their acknowledgment and resolution target instants strictly using 24/7 continuous wall-clock time from the creation event.

5. **R-21 (Mockable Test Clock)**: The application supports logical clock injection via the `X-Test-Clock` header when the environment variable `SVCDESK_TEST_CLOCK` is active. This allows deterministic, out-of-order verification of SLA breaches, pause states, and transition limits.

6. **R-23 (Persistence Across Restarts)**: All tickets and state changes are stored inside a SQLite database located at `SVCDESK_DB` (pointing to a volume mount in `/data`), ensuring persistence across container restarts.
