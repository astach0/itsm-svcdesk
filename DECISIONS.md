---
svcdesk_decisions:
  C1: wallclock
  C2: immutable
  C3: vip
---
<!-- ai-generated: 100% - generated with Gemini CLI from the course requirements and interface contract -->

# Decisions

## C1 - SLA clock for P1

**Decision:** wallclock

**Rejected alternative:** business

**Reason:** Under R-14, P1 tickets represent critical system failures affecting the entire organization where work has stopped, meaning they require round-the-clock (24/7) support. Utilizing a "wall-clock" target guarantees that a P1 ticket must be acknowledged within 15 minutes and resolved within 4 hours from its actual creation time, regardless of whether it is a weekend, holiday, or late evening. The "business" alternative would pause the SLA clocks outside the Warsaw business hours window (Monday to Friday, 08:00 to 16:00), which would allow a severe system outage on Friday evening to remain unaddressed until Monday morning without breaching SLA compliance. This is unacceptable for high-impact organizational issues, and thus the continuous wall-clock tracking is chosen.

**Service owner:** Infrastructure Operations & Support Director. This role is responsible for the overall availability of critical services and maintains the 24/7 on-call engineering schedules necessary to support high-severity incidents.

**Customer outcome:** The organization and customers receive continuous 24/7 support for critical outages, ensuring rapid response (15-minute acknowledgement) and resolution (4-hour) times to minimize overall business downtime.

## C2 - Closed tickets and reopening

**Decision:** immutable

**Rejected alternative:** reopen

**Reason:** Under R-09, a closed ticket is strictly immutable. This preserves the operational and auditing integrity of completed work and prevents historical metrics from being manipulated or skewed. If a customer reports that a previously resolved and closed issue has recurred, reopening the original ticket would distort the resolution timestamps and SLA metrics of the original incident. The correct procedure is to enforce immutability on closed tickets, forcing the creation of a new, separate ticket that explicitly references the closed one using the `related_to` field. This ensures a clean audit trail and accurate SLA accounting.

**Service owner:** IT Service Management (ITSM) Governance Manager. This role is responsible for SLA reporting, process compliance, audit trails, and the integrity of service desk metrics.

**Customer outcome:** The customer is guaranteed that their historical issues are recorded and preserved accurately. Recurrent issues are tracked under a fresh SLA clock, preventing old, closed tickets from hiding current service delivery failures.

## C3 - VIP reporters and the priority matrix

**Decision:** vip

**Rejected alternative:** matrix

**Reason:** Under R-06, tickets raised by VIP reporters must be treated with high urgency to ensure executive-level issues are visible and actionable immediately. The standard priority matrix (R-04) might compute P3 or P4 priority for VIP tickets (e.g., impact 3, urgency 3, such as a cosmetic or localized issue for an executive). Under the "vip" choice, after the priority is calculated using the standard impact/urgency matrix, any VIP ticket resulting in a P3 or P4 is automatically elevated to a minimum priority of P2. P1 and P2 priorities are left unchanged. The "matrix" alternative was rejected because it would treat VIP tickets with standard timelines (up to 72 hours for P4), failing to address the business-critical need for prompt executive support.

**Service owner:** IT Service Desk Director. This role owns the user support relationship with senior leadership and manages executive escalation procedures to maintain organizational alignment.

**Customer outcome:** High-profile leadership and executive issues receive rapid visibility and a guaranteed higher service tier (P2 minimum, with a 1-hour acknowledgement and 8-hour resolution target), ensuring corporate leadership is supported effectively.
