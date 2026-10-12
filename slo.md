---
lab3_slo:
  service: svcdesk
  route: /kb/search
  window: 28d
  slis:
    availability:
      objective: 0.99
      good: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk",http_route="/kb/search",http_response_status_code=~"2..|3..|4.."}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk",http_route="/kb/search"}[5m]))'
      error_budget: {fraction: 0.01, minutes: 403.2}
    latency:
      objective: 0.99
      threshold_seconds: 0.22
      good: 'sum(rate(http_server_request_duration_seconds_bucket{job="svcdesk",http_route="/kb/search",le="0.22"}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk",http_route="/kb/search"}[5m]))'
      error_budget: {fraction: 0.01, minutes: 403.2}
  alerts:
    - {alert: KbSearchAvailabilityFastBurn, sli: availability, burn_rate: 14.4, long_window: 1h, short_window: 5m}
    - {alert: KbSearchAvailabilitySlowBurn, sli: availability, burn_rate: 2, long_window: 6h, short_window: 30m}
---
<!-- ai-generated: 100% - drafted with Gemini CLI from requirements and load test results -->

# SLO for `GET /kb/search`

## Availability

The availability SLI measures the proportion of successful non-5xx requests (`2..`, `3..`, `4..`) relative to all valid requests to `GET /kb/search`. The objective is set to 99.0% (`0.99`), yielding an error budget fraction of 0.01 (1.0%) over a 28-day window ($28 \times 24 \times 60 = 40320$ minutes), which equals 403.2 minutes of allowed downtime or error budget per 28 days. This accounts for minor transient issues and upstream dependency behavior from `kb-index` while maintaining high reliability for IT service desk users.

## Latency

The latency SLI measures the proportion of requests completing at or below the threshold of `0.22` seconds relative to all valid requests to `GET /kb/search`. The threshold is chosen as `0.22`, which is a finite bucket boundary in our histogram ladder. The objective is set to 99.0% (`0.99`), with an error budget of 0.01 and 403.2 minutes per 28-day window.

## Alerts

| alert | SLI | burn rate | long / short window | budget spent when it fires | severity: page or chat |
|---|---|---|---|---|---|
| KbSearchAvailabilityFastBurn | availability | 14.4 | 1h / 5m | 2% in 1 hour | P1 (page) |
| KbSearchAvailabilitySlowBurn | availability | 2.0 | 6h / 30m | 5% in 6 hours | P2 (chat) |

The fast burn alert (`KbSearchAvailabilityFastBurn` with burn rate 14.4) consumes 2% of the total 28-day error budget in 1 hour, signaling a severe outage that requires immediate pager escalation (P1) to prevent rapid budget exhaustion. The slow burn alert (`KbSearchAvailabilitySlowBurn` with burn rate 2.0) consumes 5% of the error budget over 6 hours, signaling a persistent degradation that warrants notification via chat (P2) for investigation during working hours or on-call triage without emergency waking.

## Buckets

Our histogram bucket ladder is `[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.125, 0.15, 0.175, 0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.35, 0.4, 0.5, 0.75, 1.0, 1.5, 2.5, 5.0, 10.0, +Inf]`. The measured p99 ($q$) is 0.2092037 s. This falls in the bucket `(0.20, 0.22]`. The width of this bucket is 0.02 s, and its relative width is $\frac{0.02}{0.2092037} \approx 9.6\%$, which satisfies the M-11 requirement (relative width under 20%). We do not assume a dense distribution of lower latency requests beyond what is empirically observed in load testing.
