---
lab4_comms:
  awareness: 2026-10-24T07:11:26Z
  detection: 2026-10-24T07:10:39Z
  classification: 2026-10-24T07:30:00Z
  nis2:
    early_warning_due: 2026-10-25T07:11:26Z
    notification_due: 2026-10-27T07:11:26Z
    notification_sent: 2026-10-26T09:00:00Z
    final_report_due: 2026-11-26T09:00:00Z
  ksc:
    early_warning_due: 2026-10-25T07:10:39Z
    notification_due: 2026-10-27T07:10:39Z
    notification_sent: 2026-10-26T09:00:00Z
    final_report_due: 2026-11-26T09:00:00Z
  dora:
    initial_due: 2026-10-24T11:30:00Z
    initial_sent: 2026-10-24T10:00:00Z
    intermediate_due: 2026-10-27T10:00:00Z
    intermediate_sent: 2026-10-27T09:00:00Z
    final_due: 2026-11-27T09:00:00Z
  log:
    - {at: 2026-10-24T10:00:00Z, to: the financial supervisor, what: DORA initial notification of a major ICT-related incident}
    - {at: 2026-10-24T12:00:00Z, to: the CSIRT, what: NIS2 and KSC early warning}
    - {at: 2026-10-26T09:00:00Z, to: the CSIRT, what: NIS2 and KSC incident notification}
    - {at: 2026-10-27T09:00:00Z, to: the financial supervisor, what: DORA intermediate report}
---
<!-- ai-generated: 90% - drafted by Claude Code from the postmortem's instants; deadlines computed and checked by script -->

# Communications log: the regulators' clocks

The shop is assumed to fall under NIS2, the Polish KSC act and DORA, and the incident of 24 October 2026 (payment
failures at checkout, 07:08-07:16 UTC) to be significant under the first two and major under the third. Every
instant is in UTC; Warsaw leaves summer time in the night after the incident, so the Sunday deadlines read one hour
earlier on a Warsaw clock than a naive "same time tomorrow".

## The three instants you defend

**Detection (KSC), 07:10:39 UTC.** The KSC clock runs "od momentu jego wykrycia", from the moment of detection. The
first moment any system of ours registered the fault is the start of the CheckoutErrorRate firing run, the detection
instant of the postmortem; the page reached the on-call 20 s later.

**Awareness (NIS2), 07:11:26 UTC.** NIS2 counts from becoming aware of a significant incident, which needs more than
an alert: someone must know that the service is impaired. At 07:11:02 the on-call acknowledged the P1 ticket; at
07:11:26 the symptoms had been read - 7.2 % of checkout requests failing at payment, frontend traffic at six times
its baseline, three failing feature flags - and the incident was judged significant. That is the earliest instant
at which we knew, not merely suspected.

**Classification (DORA), 07:30:00 UTC.** DORA's classification as major needs the impact assessment of its technical
standard: which service, how many transactions, how long. By 07:30 service had been restored (07:16:51), the failed
orders had been counted and the duration was known, so the incident was classified as major then. It is within 24 h
of awareness, so the initial notification is due at the earlier of classification + 4 h (11:30) and awareness + 24 h
(Sunday 07:11:26): 11:30:00 UTC.

## The log

| when (UTC) | to | what | which clock |
|---|---|---|---|
| Sat 24 Oct 10:00 | the financial supervisor | DORA initial notification | DORA initial, due 11:30 the same day |
| Sat 24 Oct 12:00 | the CSIRT | NIS2 and KSC early warning | NIS2 due Sun 07:11:26, KSC due Sun 07:10:39 |
| Mon 26 Oct 09:00 | the CSIRT | NIS2 and KSC incident notification | NIS2 due Tue 07:11:26, KSC due Tue 07:10:39; final reports due 26 Nov 09:00 |
| Tue 27 Oct 09:00 | the financial supervisor | DORA intermediate report | due Tue 10:00 (72 h after the initial notification); final report due 27 Nov 09:00 |

Each report goes out before its deadline with a margin of at least an hour, and on a working day where the law
allows it: only the DORA initial notification and the early warning fall on the Saturday of the incident.
