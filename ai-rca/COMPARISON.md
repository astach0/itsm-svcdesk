<!-- ai-generated: 90% - drafted by Claude Code from the two ledgers and their queries on the snapshot -->

# Two investigators, one incident

Both investigators are the course's agent loop `agent.py` with the course's MCP server `prom_mcp.py (mcp 2.2.0)`,
on the same snapshot, asked the same question: "Checkout errors paged at 07:10:59Z on 2026-10-24. Investigate 07:00Z
to 07:20Z. What is the cause?". The first ran `qwen3:1.7b` (`ai-rca-eval.json`, transcript `ai-rca/transcript.md`,
8 tool calls in one step, 115 s), the second `qwen3:4b` (`ai-rca-eval-2.json`, transcript
`ai-rca/second/transcript.md`, 5 steps, about 50 minutes on a 4 GB GPU with 22 % of the model on the CPU). The fault
was paymentFailure (25 %), loadGeneratorFloodHomepage and recommendationCacheFailure.

## Where they agreed

Both named checkout as the place of the symptom: 1.7b's H4 ("The alert is tied to the **checkout service**") and
4b's H5 (checkout errors "cascade from payment failures"). Both are true on the data - 7.4 % of checkout requests
failed in the window to 07:13 and none on the baseline - but 1.7b only restated the CheckoutErrorRate alert it read
through `alerts_at`, while 4b explained it by a dependency it found in the span names.

## Where they parted

- **The cause.** 1.7b blamed "excessive load on the checkout service" from the load generator (H1, hallucinated:
  checkout's traffic was 0.099/s against 0.088/s on the baseline). 4b blamed "**PaymentService/Charge failures**"
  (H1, correct: Charge errors at 0.0073/s at 07:13, none on the baseline). The data proved 4b right: every failed
  order was a failed charge.
- **The load.** 1.7b's H2 saw the load-generator surge, and the surge was real (25.3 client calls/s against 2.26 on
  the baseline): it is the only one of the three faults either agent touched beyond payment. It got the mechanism
  wrong (POST calls did not rise; the flood was home-page GETs), so partially correct. 4b never looked at traffic.
- **The mechanism of the payment failure.** 4b's two numbered hypotheses invented one: timeouts at an external
  gateway (H3, hallucinated: payment's p95 was 3.3 ms) and rate limiting or overload (H4, hallucinated: payment's
  traffic did not change). The failures were fast rejections at unchanged load.
- **Time.** 4b put the spike at 07:17:20 (H2, partially correct: right component, wrong time); it read the
  cumulative error counter, flat at 2 after the last failure, as a rate. The errors ended at 07:11:41.
- **Noise.** 1.7b claimed errors on cart endpoints (H3, hallucinated: cart never produced an error span) and closed
  with an unfalsifiable "backend service bottleneck or resource exhaustion" (H5).

## Verdict

4b found the user-facing cause, payment, and its link to checkout; 1.7b did not, but it was the only one to notice a
second fault, the traffic flood. Neither found the third fault, recommendationCacheFailure, whose latency doubled
but stayed under 50 ms. Both went beyond the alert only where they queried the span metrics themselves; both invented
a mechanism for what they found. The larger model was right more often (2 correct, 1 partial, 2 hallucinated against
0, 2 and 2 with one unfalsifiable) at about 25 times the run time on this machine.
