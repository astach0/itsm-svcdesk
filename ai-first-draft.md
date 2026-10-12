---
lab3_first_draft:
  source: ai
  tool: "ChatGPT (GPT-6), this conversation, 12 October 2026"
  ladder: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
  verdict: TODO
  evidence: {p99_seconds: TODO, bucket: [TODO, TODO], relative_width: TODO}
lab3_flawed_ladder:
  verdict: refuted
  evidence: {p99_seconds: TODO, bucket: [TODO, TODO], relative_width: TODO}
---
<!-- ai-generated: 100% - initial draft generated with ChatGPT; measurement evidence and final verdicts will be completed from lab results -->

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

TODO: after measuring, calculate the p99, its bucket, the relative width and whether the ladder resolves the p99 according to M-11.

## The draft alert rule

TODO: explain how the first-draft alert behaves for the chosen SLO and what was retained or changed in the final alert rules.

## Verdict on the instructor's flawed ladder

TODO: use the same measured p99 to calculate the bucket and relative width of the instructor's flawed ladder.