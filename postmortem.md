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
<!-- ai-generated: 90% - drafted by Claude Code from the snapshot, the incident watcher's log and itsmlab incident 4 -->

# Postmortem: shop orders failing at payment, with a home-page traffic flood and a recommendation cache leak

## Date

The incident happened on Saturday 24 October 2026 between 07:08 and 07:17 UTC; this postmortem was written the same
morning, from the committed snapshot.

## Authors

Written by the on-call engineer of the Lab 4 playground (repository owner astach0), with Claude Code as assistant.

## Status

Complete for the incident: service restored at 07:16:51 UTC and the ticket resolved; action items in progress.

## Summary

For about three and a half minutes a quarter of the shop's payments were rejected, so orders failed at checkout;
at the same time the home page received fifteen times its normal traffic and the recommendation service started to
leak cache memory. CheckoutErrorRate paged after 153 s and all three faults were switched off within nine minutes.

## Impact

Orders: checkout's server-span counter rose from 68 to 103 calls between 07:07 and 07:12 UTC (about 35 orders), and
its error counter from 0 to 2 - two orders failed at payment
(`sum(traces_span_metrics_calls_total{service_name="checkout", span_kind="SPAN_KIND_SERVER", status_code="STATUS_CODE_ERROR"})`).
Over the 5-minute window ending 07:13 the failure ratio was 7.4 % of checkout requests, against none on the
baseline (the CheckoutErrorRate expression). Every failure was a payment failure: payment's error counter shows the
same two calls. No checkout request slowed down: checkout's p95 stayed at 48 ms (49.9 ms on the baseline).
Traffic: the frontend served up to 73.7 requests/s
(`max_over_time(sum(rate(traces_span_metrics_calls_total{service_name="frontend", span_kind="SPAN_KIND_SERVER"}[2m]))[10m:1m])`
at 07:16) against 4.8/s on the baseline and 3.3/s at 07:19; its p95 never exceeded 48 ms, so users did not feel it.
Recommendation: its p95 rose from about 21 ms to a peak of 44.7 ms (5-minute window) before the flag was switched
off; no request failed. No user was affected after 07:11:41, when payment was restored.

## Root Causes

Three faults were active at once, each a feature flag the course injector switched on. paymentFailure (25 %) made
the payment service reject a quarter of its charges, and checkout returned those failures to the shop's users as
failed orders. loadGeneratorFloodHomepage made the load generator request the home page about fifteen times as
often, loading frontend-proxy and frontend. recommendationCacheFailure made the recommendation service's cache grow
without bound, raising its latency and memory. Only the first reached the users; the other two were capacity risks
that would have turned into user-facing failures had they run longer.

## Trigger

At 07:08:05 UTC the injector changed the three flags' default variants; the first sample of the fault series is at
07:08:06 UTC (the onset). It is a configuration change pushed at run time, with no deployment and no code change.

## Resolution

The flags were switched off through the injector one at a time, the user-facing fault first: paymentFailure at
07:11:41 (payment and checkout errors went to zero in the next minute), loadGeneratorFloodHomepage at 07:14:36
(frontend traffic fell back to 3.3 requests/s by 07:19), recommendationCacheFailure at 07:16:51. One at a time, so
that each change's effect could be seen before the next; the order follows user impact. The detecting alert
resolved at 07:15:39 and the pager received the resolved notification at 07:15:59.

## Detection

CheckoutErrorRate (P1, checkout server-span error ratio above 5 % over 5 minutes, `for: 1m`) started firing at
07:10:39 UTC, 153 s after the onset (MTTD), and paged at 07:10:59; the P1 ticket was opened at 07:11:01 and
acknowledged at 07:11:02 (MTTA 23 s). About 100 s of the MTTD come from the 5-minute window filling with failures at
0.13 orders/s, the rest from `for: 1m`. No alert saw the other two faults: neither the traffic flood nor the
recommendation latency crossed a threshold of any rule. Without CheckoutErrorRate the first signal would have been
customers whose orders failed, through the help desk.

## Action Items

| Action Item | Type | Owner | Bug |
|---|---|---|---|
| Add a P3 chat alert on frontend request rate above three times its 1-hour average, so that a traffic flood is visible before it saturates the shop | prevent | on-call / monitoring owner | ITSM-101 |
| Add a P3 chat alert on recommendation p95 latency and memory growth, so that a cache leak is seen before it degrades recommendations | prevent | recommendation service owner | ITSM-102 |
| Add a P2 alert on payment's own server error ratio, so that the cause service is named next to the checkout page | mitigate | payment service owner | ITSM-103 |
| Record every feature-flag change with its time in the change log and show it on the shop dashboard, so that "what changed?" is answered in one place | process | release / change manager | ITSM-104 |

## Lessons Learned

### What went well

The page reached the on-call 20 s after the alert started firing and the P1 ticket was acknowledged 23 s after
detection. Switching the flags off one at a time made each fault's effect visible on its own, and restoring payment
first ended the user impact 39 s after the acknowledgement. The routing worked as designed: the P1 reached the
pager, and its resolved notification followed when the alert ended.

### What went wrong

Two of the three faults raised no alert at all; they were found only by reading the flag state. The detecting alert
resolved at 07:15:39 while two flags were still failing, so the recorded MTTR (453 s) ends before the last fault did.
At the shop's low order rate, two failed orders are enough to move the 5-minute error ratio across 5 %, so the same
rule may fire late, or not at all, on a smaller payment failure.

### Where we got lucky

The injector drew 25 % rather than 50 % for paymentFailure, and the traffic flood did not raise the frontend's latency.
The recommendation leak was switched off after nine minutes, before its memory growth led to restarts.

## Timeline

All times UTC, 24 October 2026.

- 07:04:20 - the injector was armed after a quiet baseline: no alert pending or firing, no P1 in the last 10 minutes.
- 07:08:05 - the injector switched on paymentFailure (25 %), loadGeneratorFloodHomepage and recommendationCacheFailure.
- 07:08:06 - onset: first sample of the fault series.
- 07:09:50 - CheckoutErrorRate pending.
- 07:10:39 - detection: CheckoutErrorRate (P1) firing.
- 07:10:59 - the pager received the P1 page for CheckoutErrorRate.
- 07:11:01 - P1 ticket 5c19b066-c079-4cd3-ae98-790aec6cfbcc opened.
- 07:11:02 - acknowledgement of the ticket.
- 07:11:26 - symptoms read: checkout and payment 7.2 % errors, frontend at 31.7 requests/s against 4.8 on the baseline; the injector's flags.json showed the three failing flags.
- 07:11:41 - paymentFailure switched off; payment errors were zero by 07:14.
- 07:14:36 - loadGeneratorFloodHomepage switched off.
- 07:15:39 - recovery: CheckoutErrorRate stopped firing; resolved notification on the pager at 07:15:59.
- 07:16:51 - recommendationCacheFailure switched off; no flag failing.
- 07:17:14 - ticket resolved.
- 07:19:12 - Prometheus snapshot taken.
- After the snapshot, the AI investigator (qwen3:1.7b) was scored in ai-rca-eval.json. None of its hypotheses was acted on during the incident; its best one, H2 (load-generator surge), is confirmed by `sum(rate(traces_span_metrics_calls_total{service_name="load-generator", span_kind="SPAN_KIND_CLIENT"}[5m])) > 10`, 25.3/s at 07:13, with the wrong mechanism (POST calls stayed at 0.74/s).

## Supporting information

The snapshot `incident/tsdb-snapshot.tar.gz` and the ticket `incident/ticket.json`; `itsmlab incident 4` printed
onset 07:08:06Z, detection 07:10:39Z (CheckoutErrorRate), acknowledgement 07:11:02Z, recovery 07:15:39Z, MTTD 153 s,
MTTA 23 s, MTTR 453 s, with no baseline warning. The rules are in `prometheus/demo-alerts.yml`, the routing tree in
`alertmanager/alertmanager.yml`, the AI ledger in `ai-rca-eval.json` with its transcript `ai-rca/transcript.md`.

## Problem record

- Incident record: P1 ticket 5c19b066-c079-4cd3-ae98-790aec6cfbcc, opened 07:11:01 and resolved 07:17:14 UTC when service was restored.
- Root cause: feature flags can be switched to failing variants at run time with no alert on the change and no alert on two of the three fault classes (traffic, cache growth).
- Known error: a failing paymentFailure flag rejects a share of payments and fails orders at checkout; a home-page flood and a recommendation cache leak go unalerted.
- Workaround: switch the failing flags off through the flag service, payment first, and watch the checkout error ratio return to zero.
