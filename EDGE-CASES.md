---
lab2_edge_cases:
  E1: {rule: R-08, count: 3}
  E2: {rule: R-06, count: 2}
  E3: {rule: R-09, count: 4}
  E4: {rule: R-10, count: 4}
  E5: {rule: R-12, count: 1}
  E6: {rule: R-13, count: 11}
---
<!-- ai-generated: 100% - generated from the published Lab 2 fixture and METRIC-SPEC.md; explanations reviewed for rule alignment -->

# Edge cases in the practice event log

## E1 - clock skew produces a negative lead time

- What the log contains: Three successful production lead-time pairs have deployment timestamps that occur before the commit timestamp. They are clock-skew anomalies rather than evidence that delivery happened before the code existed.
- What a default definition would have done: A conventional calculation might discard negative durations as impossible, or report a negative lead time that distorts the median and hides the data-quality problem.
- Why the rule is defensible: R-08 keeps the pair, clamps its duration to zero, and counts the anomaly. That preserves the fact that the commit was delivered while preventing timestamp disagreement from producing a misleading negative performance value.

## E2 - a revert of a revert

- What the log contains: Two commits have non-null reverts. The second revert points to the first revert, so the chain must be followed transitively back to the original change rather than treating the three commits as three independent changes.
- What a default definition would have done: A commit-counting definition could create a new change for each revert commit and inflate the number of changes, lead-time pairs, and delivered work.
- Why the rule is defensible: Reverts are corrective actions on an existing change, so R-06 preserves the original change identity through the whole chain and prevents operational rollback mechanics from manufacturing throughput.

## E3 - a hotfix that never touched main

- What the log contains: Four distinct deployed commits come from hotfix branches instead of branch main. They nevertheless reach production through successful or failed production deployments inside the observation window.
- What a default definition would have done: A main-branch-only calculation would discard these commits and understate the work that actually reached production, especially for emergency fixes made directly on a hotfix branch.
- Why the rule is defensible: R-09 defines production delivery independently of branch naming. A change is delivered because the deployment carried it, not because it happened to pass through a particular branch.

## E4 - a deployment with zero linked commits

- What the log contains: Four production deployments contain an empty commits array. They are still real deployment events with timestamps and outcomes.
- What a default definition would have done: A definition that filters out deployments with no commits would undercount deployment frequency and would also change the denominator used by the two instability rates.
- Why the rule is defensible: R-10 deliberately treats an empty deployment as a deployment event even though it cannot form a commit-to-deployment lead-time pair. This keeps the event log internally consistent across throughput and instability metrics.

## E5 - a deployment that failed and never recovered

- What the log contains: One failed production deployment has no covering incident that resolves it within the supplied evidence. It therefore remains an open failure.
- What a default definition would have done: A dashboard implementation might invent a recovery time by stopping the clock at the end of the observation window, or remove the failure from the recovery metric entirely without showing it anywhere else.
- Why the rule is defensible: R-12 excludes unrecovered failures from the recovery-time median because no recovery occurred, but keeps them in the failure-rate denominator and reports them explicitly as open failures.

## E6 - overlapping incidents

- What the log contains: Eleven unordered pairs of incident intervals intersect when each incident is represented by [opened, resolved), or by [opened, window.to) when it remains unresolved.
- What a default definition would have done: A naive calculation might merge overlapping incidents into one outage or add their durations, either of which changes the number of recoveries attributed to failed deployments.
- Why the rule is defensible: R-13 measures recovery per failed deployment and chooses the earliest covering incident. Overlap is therefore an observable property of the incident data, not a reason to double-count elapsed time.

## Gaming demonstration

The improved metric is `deployment_frequency_per_day`, using R-11. The after-log adds eleven successful empty production deployments, which raises frequency from 2.0 to 2.523810 deployments per day, clearing the required +25% margin. At the same time, the experiment changes three original successful deployments so that they carry no commits. Those base deployments remain present with the same id, timestamp, environment, and outcome, so the record is conserved under R-19; only their commit lists are changed, which R-19 explicitly permits. For the base work alone, the service then reports 57 delivered changes instead of 65, which is at most 90% of the original and therefore satisfies R-21. A real team could be rewarded for deployment frequency and respond by creating many low-value or empty deployment events while allowing substantive work to disappear from individual deployments. The incentive belongs to the team or manager whose scorecard rewards a higher deployment count, while the engineering organization and downstream customers carry the cost through lower delivery of the original work.
