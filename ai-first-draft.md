---
lab3_first_draft:
  source: ai
  tool: "ChatGPT (GPT-6), this conversation, 12 October 2026"
  ladder: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
  verdict: refuted
  evidence: {p99_seconds: 0.2065, bucket: [0.1, 0.25], relative_width: 0.726}
lab3_flawed_ladder:
  verdict: refuted
  evidence: {p99_seconds: 0.2065, bucket: [0.04, 0.5], relative_width: 2.228}
---
<!-- ai-generated: 100% - initial draft generated with ChatGPT; measurement evidence and verdicts completed from the latest load-test results -->

# The assistant's first draft, and two verdicts

## Prompt

Before any load test or measured p99 is available, recommend histogram bucket boundaries in seconds and a Prometheus alert rule for a service implementing GET /kb/search. Assume the metric is http_server_request_duration_seconds with labels http_request_method, http_route and http_response_status_code, and that /kb/search is the route template. Propose an initial ladder and one actionable burn-rate alert for a 99% availability SLO. Explain the choices and limitations. Do not invent measured latency values.

## Answer

For an initial draft, I would use the following commonly used histogram bucket boundaries in seconds:

[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]

This is a conventional starting point, similar to the default Prometheus Go client buckets. It covers a broad range of request durations, but it is not tailored to the actual latency distribution of /kb/search. In particular, it may have insufficient resolution around the measured p99. After collecting a representative load test, I would replace it with a denser ladder around the observed p99 and its expected variation.

For a 99% availability objective, a fast burn-rate alert can compare the fraction of failed requests with 14.4 times the allowed error fraction. With a 1% error budget, the threshold is 14.4 × 0.01 = 0.144, or 14.4% failed requests. Using both a short and a long window helps distinguish a sustained incident from a short-lived spike.

Example initial alert rule:

```yaml
groups:
  - name: kb-search
    rules:
      - alert: KbSearchErrorsBurnFast
        expr: |
          (
            sum(rate(http_server_request_duration_seconds_count{
              job="svcdesk",
              http_route="/kb/search",
              http_response_status_code=~"5.."
            }[5m]))
            /
            sum(rate(http_server_request_duration_seconds_count{
              job="svcdesk",
              http_route="/kb/search"
            }[5m]))
          ) > (14.4 * (1 - 0.99))
          and
          (
            sum(rate(http_server_request_duration_seconds_count{
              job="svcdesk",
              http_route="/kb/search",
              http_response_status_code=~"5.."
            }[1h]))
            /
            sum(rate(http_server_request_duration_seconds_count{
              job="svcdesk",
              http_route="/kb/search"
            }[1h]))
          ) > (14.4 * (1 - 0.99))
        for: 5m
        labels:
          service: svcdesk
          slo: availability
          severity: P1
        annotations:
          summary: "Fast error-budget burn on /kb/search"
```

This is only a first draft, not a validated final rule. The bucket ladder must be judged against the actual load-test measurement, and the alert expression must be tested against the required firing, quiet-period, reset and mutation cases.

## Verdict on the draft ladder

The latest load test measured the application p99 ($q$) at 0.2065 seconds (206.5 ms), and direct `kb-index` p99 ($q_{kb}$) at 208.2 ms ($q \ge 0.9 \times q_{kb}$, satisfying the non-bypass condition). The histogram-derived application p99 is 0.2058 seconds, with a relative difference of about 0.34% from $q$ (well within the M-12 maximum of 25%).

The assistant's initial draft ladder places $q$ in the bucket (0.1, 0.25] seconds. The bucket width is 0.15 seconds, and its relative width is $0.15 / 0.2065 \approx 0.726$ (72.6% of $q$). This exceeds the M-11 maximum of 20%, so the assistant's initial draft ladder is refuted.

In contrast, the refined service bucket ladder introduces denser boundaries around $q$, placing it in bucket (0.20, 0.22] seconds with a bucket width of 0.02 seconds and a relative width of $0.02 / 0.2065 = 9.7\%$ (PASS, below the 20% limit).

## The draft alert rule

The draft proposes a 99% availability objective and a fast burn-rate alert with a 14.4 burn-rate multiplier, requiring the error ratio to exceed the threshold in both a 5-minute and a 1-hour window, with a 5-minute pending period. The expression uses server-error responses (HTTP 5xx) as the bad-event numerator and all requests to `/kb/search` as the denominator. It is only a proposal: it has not yet been validated against the lab's alert tests or mutation tests. The final alert rules must use the objective and windows justified in `slo.md`, and must pass the firing, quiet-period, reset and mutation tests.

## Verdict on the instructor's flawed ladder

Using the measured application p99 of 0.2065 seconds, the instructor's flawed reference bucket (0.04, 0.5] has a width of $0.5 - 0.04 = 0.46$ seconds, and a relative width of $0.46 / 0.2065 \approx 2.228$ (222.8% of $q$). This is far above the M-11 limit of 20%, so the instructor's flawed ladder fails M-11 (refuted). Although it has fine boundaries at short durations, it lacks sufficient resolution around the measured p99.
