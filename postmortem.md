---
lab4_postmortem:
  ticket: "5c19b066-c079-4cd3-ae98-790aec6cfbcc"
  detecting_alert: CheckoutErrorRate
  onset: 2026-10-24T07:08:06Z
  detection: 2026-10-24T07:10:39Z
  acknowledgement: 2026-10-24T07:11:02Z
  recovery: 2026-10-24T07:15:39Z
  mttd_seconds: 153
  mtta_seconds: 23
  mttr_seconds: 453
  identified_flags: [paymentFailure, loadGeneratorFloodHomepage, recommendationCacheFailure]
---
<!-- ai-generated: 90% - drafted by Claude Code from the snapshot, the incident watcher's log and itsmlab incident 4; every number re-queried on the served snapshot on 26 October -->

# Postmortem: shop orders failing at payment, with a home-page traffic flood and a recommendation memory leak

## Date

The incident happened on Saturday 24 October 2026 between 07:08 and 07:17 UTC. This postmortem was first written
the same morning from the committed snapshot, and revised on 26 October after every number was re-queried on it.

## Authors

Written by the on-call engineer of the Lab 4 playground (repository owner astach0), with Claude Code as assistant.

## Status

Complete for the incident: the ticket was resolved at 07:17:14 UTC, after the last failing flag was switched off at
07:16:51. Action items open; the problem record stays open until they are done.

## Summary

From 07:08 to 07:11:41 UTC the payment service was set to reject a quarter of its charges: 2 of the 28 orders placed
in that time failed at checkout. At the same time the home page received about twelve times its normal traffic and
the recommendation service leaked memory. CheckoutErrorRate paged after 153 s, the payment fault was switched off
39 s after the acknowledgement, and all three faults were off by 07:16:51.

## Impact

All figures are read from the snapshot. The queries are listed under Supporting information as Q1 to Q8.

- **Failed orders.** 28 orders reached checkout while the payment fault was on: checkout's server-span counter (Q1)
  went from 75 at 07:08 to 103 at 07:12. Its error counter (Q2) went from 0 to 2 in the span-metric export of
  07:09:40, and stayed at 2 to the end of the snapshot. Payment's own error counter shows the same two calls, so
  every failed order was a rejected charge. The 5-minute failure ratio, the CheckoutErrorRate expression (Q3), was
  7.5 % at 07:10, 7.2 % at 07:11:26 and 7.4 % at 07:13. It was zero on the baseline.
- **Checkout latency.** Checkout's p95 (Q4) rose from 50-83 ms on the baseline (07:00-07:07) to 132.5 ms in the
  windows ending 07:09 and 07:10, and was back at 48 ms by 07:13. That is noticeable in the data but far below the
  2 s of CheckoutLatencyHigh; no user waited long.
- **Traffic.** The frontend (Q5, 2-minute rate) served 3.2-4.3 requests/s on the baseline and 45-54/s from 07:10 to
  07:14. The last reading under the flood was 73.7/s at 07:15, in a window that ended just after the flag went off
  at 07:14:36. It fell to 7.0/s at 07:16 and 4.0/s at 07:17. No frontend request failed, and its p95 (Q6) fell from
  44-49 ms to 31-42 ms, because the flood consisted of cheap home-page requests. Users did not feel it.
- **Recommendation.** The service's resident memory (Q7) was flat at 69.7 MB on the baseline. It reached 70.2 MB
  by 07:13, 72.5 MB by 07:16 and 81.3 MB by 07:18, growing faster every minute: +0.2 MB from 07:08 to 07:13, +11 MB
  from 07:13 to 07:18. After the flag went off it stopped growing, but the memory was not released: still
  81.3 MB at 07:19, when the snapshot was taken. No recommendation request failed (Q8 returns nothing).
  Its p95 is too noisy to measure the fault: it was already 30-35 ms on the baseline (07:05-07:08), and 36-45 ms
  in 07:14-07:16.

User impact ended at 07:11:41, when payment was restored. No failed charge was recorded after 07:09:40.

## Root Causes

Three faults were active at once. Each was a feature flag that the course injector switched to a failing variant:

- **paymentFailure (25 %).** The payment service rejected each charge with a probability of 25 %. Checkout passed
  the rejection on to the shop's user as a failed order. In this run only 2 of 28 charges failed (7 %).
- **loadGeneratorFloodHomepage.** The load generator requested the home page about twelve times as often as usual,
  loading frontend-proxy and frontend.
- **recommendationCacheFailure.** The recommendation service's in-process cache grew without bound. Switching the
  flag off stops the growth but does not release the memory already taken; only a restart does.

Only the first reached users. The other two were capacity risks that would have become user-facing failures had they
run longer. What was already wrong in the system:

- flags can be switched to failing variants at run time with no record of the change and no alert on it;
- no alert watched shop traffic or service memory;
- the one rule that saw the fault needed two failed orders in five minutes to fire (see Detection).

## Trigger

At 07:08:05 UTC the injector changed the three flags' default variants; the first sample of the fault series is at
07:08:06 UTC (the onset). It is a configuration change pushed at run time, with no deployment and no code change.

## Resolution

The flags were switched off through the injector one at a time, the user-facing fault first:

- **paymentFailure at 07:11:41.** No failed charge had been recorded since 07:09:40, and none was afterwards.
- **loadGeneratorFloodHomepage at 07:14:36.** Frontend traffic fell to 7.0 requests/s at 07:16 and 4.0/s at 07:17.
- **recommendationCacheFailure at 07:16:51.** Recommendation memory stopped growing at 81.3 MB. The service was not
  restarted, so the leaked memory stayed allocated.

Switching one flag at a time made each change's effect visible before the next one; the order follows user impact.
CheckoutErrorRate's expression became false at 07:13:40, when the two failures of 07:09:40 slid out of its 5-minute
window. `keep_firing_for: 2m` then held the alert until 07:15:39, the recovery, and the pager received the resolved
notification at 07:15:59.

## Detection

CheckoutErrorRate detected the incident. It is a P1 rule: checkout server-span error ratio above 5 % over 5
minutes, with `for: 1m` and `keep_firing_for: 2m`.

**Timing.** It went pending at 07:09:40 and started firing at 07:10:39 UTC, 153 s after the onset (MTTD). It paged
at 07:10:59; the P1 ticket was opened at 07:11:01 and acknowledged at 07:11:02 (MTTA 23 s). The MTTD splits into two
parts. 94 s passed before any failed charge reached Prometheus: both arrived in the span-metric export of 07:09:40,
and checkout's span metrics are exported once a minute. The remaining 59 s are the rule's `for: 1m`.

**Sensitivity.** At the shop's rate of about 0.1 orders/s, one failed order in the window makes a ratio of about
3.7 %, under the threshold. The rule fired only because both failures fell into the same window.

**What went unseen.** No other alert went pending or firing between 07:00 and 07:19: the traffic flood and the
memory leak crossed no rule, because none exists for them. Without CheckoutErrorRate, the first signal would have
been customers reporting failed orders to the help desk.

## Action Items

| Action Item | Type | Owner | Bug |
|---|---|---|---|
| Add a P3 chat alert when the frontend's 5-minute request rate exceeds three times its 1-hour average (`sum(rate(traces_span_metrics_calls_total{service_name="frontend", span_kind="SPAN_KIND_SERVER"}[5m])) > 3 * avg_over_time(sum(rate(traces_span_metrics_calls_total{service_name="frontend", span_kind="SPAN_KIND_SERVER"}[5m]))[1h:1m])`), so that a traffic flood is visible before it saturates the shop; on this snapshot it is true from 07:10 to 07:15 and never on the baseline | prevent | on-call / monitoring owner | ITSM-101 |
| Add a P3 chat alert on recommendation memory growth (`delta(process_runtime_cpython_memory_bytes{service_name="recommendation", type="rss"}[10m]) > 1e7`, more than 10 MB in 10 minutes, above the 5.6 MB it grew while warming up on the baseline), not on its p95, which moved from 8 to 35 ms on the baseline with no fault; on this snapshot it would have fired only at 07:18, so it catches a leak that runs longer than this one | prevent | recommendation service owner | ITSM-102 |
| Add a P2 alert on payment's own server error ratio, so that the alert names the cause service next to the checkout symptom | mitigate | payment service owner | ITSM-103 |
| Record every feature-flag change with its time and author in the change log, post it to the chat channel and show it on the shop dashboard, so that "what changed?" is answered in one place | process | release / change manager | ITSM-104 |
| Make the checkout page independent of the order rate: page also when `sum(increase(traces_span_metrics_calls_total{service_name="checkout", span_kind="SPAN_KIND_SERVER", status_code="STATUS_CODE_ERROR"}[10m])) >= 1` persists for 1 minute, since the shop has no failed orders on a healthy day and one failure in five minutes stays under the 5 % ratio | mitigate | on-call / monitoring owner | ITSM-105 |
| Make the recommendation service drop its cache when recommendationCacheFailure is switched off, and until then add "restart recommendation and check its memory is back near 70 MB" to the workaround | mitigate | recommendation service owner | ITSM-106 |
| Write a runbook for the shop P1: read the flag state first, switch the user-facing flag off first, record each revert in the ticket, and resolve the ticket only when no flag is failing and memory is back to baseline | process | on-call lead | ITSM-107 |

## Lessons Learned

### What went well

- The page reached the on-call 20 s after the alert started firing, and the P1 ticket was acknowledged 23 s after
  detection.
- Reading the flag state at 07:11:26 named all three faults at once, and restoring payment first ended the user
  impact 39 s after the acknowledgement.
- Switching the flags off one at a time made each fault's effect visible on its own.
- The routing worked as designed: the P1 reached the pager, and its resolved notification followed when the alert
  ended.

### What went wrong

- Two of the three faults raised no alert at all; they were found only by reading the flag state.
- The detecting alert does not measure the fault's end. Its recovery (07:15:39) is the last failure plus the 5-minute
  window plus `keep_firing_for: 2m`. That is four minutes after payment was restored and more than a minute before
  the last flag went off. The recorded MTTR (453 s) therefore says little about how long users were affected
  (07:08:06-07:11:41) or how long the incident lasted (to 07:16:51).
- At the shop's order rate, CheckoutErrorRate needs two failed orders in five minutes. A smaller payment failure
  could have gone unpaged.
- The recommendation service kept its leaked memory after the fix, because the workaround did not include a restart.

### Where we got lucky

- The 25 % payment failure produced only 2 failed orders out of 28; the expected number was 7.
- Both failures fell into the same export, so the ratio crossed 5 % at once; one failure alone would not have paged.
- The flood of cheap home-page requests did not raise the frontend's latency.
- The memory leak was stopped early on its accelerating curve, at 81 MB, long before a restart or an out-of-memory
  kill.

## Timeline

All times UTC, 24 October 2026.

- 07:04:20 - the injector was armed after a quiet baseline: no alert pending or firing, no P1 in the last 10 minutes.
- 07:08:05 - the injector switched on paymentFailure (25 %), loadGeneratorFloodHomepage and recommendationCacheFailure.
- 07:08:06 - onset: first sample of the fault series.
- 07:09:40 - the span-metric export carried checkout's first two errors, both rejected charges; CheckoutErrorRate
  pending (ratio 5.8 %).
- 07:10:39 - detection: CheckoutErrorRate (P1) firing.
- 07:10:59 - the pager received the P1 page for CheckoutErrorRate.
- 07:11:01 - P1 ticket 5c19b066-c079-4cd3-ae98-790aec6cfbcc opened.
- 07:11:02 - acknowledgement of the ticket.
- 07:11:26 - symptoms read: 7.2 % of checkout and payment requests failing (Q3), frontend at 31.7 requests/s
  (5-minute rate) against 3.7-4.8 on the baseline. The injector's flags.json showed the three failing flags.
- 07:11:41 - paymentFailure switched off: end of user impact.
- 07:13:40 - the two failures left the 5-minute window and CheckoutErrorRate's expression became false;
  `keep_firing_for` kept the alert firing.
- 07:14:36 - loadGeneratorFloodHomepage switched off.
- 07:15:39 - recovery: CheckoutErrorRate stopped firing; resolved notification on the pager at 07:15:59.
- 07:16:51 - recommendationCacheFailure switched off; no flag failing.
- 07:17:14 - ticket resolved.
- 07:18:00 - recommendation memory stopped growing at 81.3 MB; it was not released.
- 07:19:12 - Prometheus snapshot taken.
- After the snapshot, the AI investigator (qwen3:1.7b) was scored in ai-rca-eval.json. None of its hypotheses was
  acted on during the incident. Its best one, H2 (load-generator surge), is confirmed by
  `sum(rate(traces_span_metrics_calls_total{service_name="load-generator", span_kind="SPAN_KIND_CLIENT"}[5m])) > 10`
  (25.3/s at 07:13), but with the wrong mechanism: POST calls stayed at 0.74/s.

## Supporting information

The snapshot `incident/tsdb-snapshot.tar.gz` and the ticket `incident/ticket.json`. `itsmlab incident 4` printed
onset 07:08:06Z, detection 07:10:39Z (CheckoutErrorRate), acknowledgement 07:11:02Z, recovery 07:15:39Z, MTTD
153 s, MTTA 23 s and MTTR 453 s, with no baseline warning. The rules are in `prometheus/demo-alerts.yml`, the
routing tree in `alertmanager/alertmanager.yml`, and the AI ledger in `ai-rca-eval.json` with its transcript
`ai-rca/transcript.md`.

The queries behind Impact, Detection and the Timeline, all run on the served snapshot at 1-minute steps from 07:00
to 07:20 (`metric` is `traces_span_metrics_calls_total`, `ms` is `traces_span_metrics_duration_milliseconds_bucket`):

- Q1 `sum(metric{service_name="checkout", span_kind="SPAN_KIND_SERVER"})`
- Q2 `sum(metric{service_name="checkout", span_kind="SPAN_KIND_SERVER", status_code="STATUS_CODE_ERROR"})`, and the
  same with `service_name="payment"`
- Q3 the CheckoutErrorRate expression: `sum(rate(metric{service_name="checkout", span_kind="SPAN_KIND_SERVER", status_code="STATUS_CODE_ERROR"}[5m])) / sum(rate(metric{service_name="checkout", span_kind="SPAN_KIND_SERVER"}[5m]))`
- Q4 `histogram_quantile(0.95, sum by (le) (rate(ms{service_name="checkout", span_kind="SPAN_KIND_SERVER"}[5m])))`
- Q5 `sum(rate(metric{service_name="frontend", span_kind="SPAN_KIND_SERVER"}[2m]))`, and `[5m]` for the baseline range
  and the 07:11:26 reading
- Q6 Q4 with `service_name="frontend"`
- Q7 `process_runtime_cpython_memory_bytes{service_name="recommendation", type="rss"}`
- Q8 `sum(rate(metric{service_name="recommendation", span_kind="SPAN_KIND_SERVER", status_code="STATUS_CODE_ERROR"}[5m]))`
- `count by (alertname, alertstate) (ALERTS)` for which alerts were pending or firing, and when

## Problem record

- Incident record: P1 ticket 5c19b066-c079-4cd3-ae98-790aec6cfbcc, opened 07:11:01 and resolved 07:17:14 UTC when service was restored.
- Root cause: feature flags can be switched to failing variants at run time with no record or alert on the change, the shop has no alert on traffic or memory, and the checkout alert needs two failed orders in five minutes (ITSM-101 to ITSM-105).
- Known error: a failing paymentFailure flag rejects a share of charges and fails orders at checkout; a home-page flood and a recommendation cache leak go unalerted, and the leaked memory stays allocated after the flag is switched off.
- Workaround: switch the failing flags off through the flag service, payment first, and watch the checkout error ratio return to zero; then restart the recommendation service and check that its memory is back near 70 MB.
