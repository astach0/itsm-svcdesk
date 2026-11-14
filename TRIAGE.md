---
lab5_triage:
  image: ghcr.io/astach0/itsm-svcdesk@sha256:dd1cc6c4bf86c26cac44fa303626e77fb463a783779db858015f6f0b29d1ee69 # main @ a66a4d0, run 43595750525 (P-10)
  sarif_receipt: 384                                       # swasik/itsm-2026-submissions#384, receipt of d81ce6f (P-10)
---
<!-- ai-generated: 95% - Claude Code (Opus 5.5) ran the scanners locally and in CI, made the fixes and wrote the rows and the Bake-off from this repository's runs; I chose the decisions -->
# Triage

What the gates and the reporting scanners found on my service, and what I did about each (CI-SPEC.md P-11, P-12).
One row per rule of one tool; a row may cover several locations, and the Reason says which. Tool is the tool id of
P-15 (`trivy`, `grype`, `osv-scanner`, `gitleaks`, `semgrep`). Decision is one of `fix`, `ignore`,
`false-positive`, `accept`.

The first image scan (Trivy 0.74.0, `--ignore-unfixed`, HIGH/CRITICAL, the old `FROM python:3.13-slim` and FastAPI
0.115.0) failed the `image` gate on 14 IDs in 18 package findings. Three changes removed all of them, with nothing in
`.trivyignore`: the base image pinned to the 2026-11-05 digest of `python:3.13-slim` plus `apt-get upgrade` (the
Debian rows), FastAPI 0.115.0 -> 0.162.7 with starlette 1.10.0 and certifi 2026.10.23 pinned in `requirements.txt`
(the Python rows; the 12 tests of `tests/` still pass), and `pip uninstall -y pip` at the end of the install layer
(the rows of packages that only pip vendors in `pip/_vendor`; svcdesk never calls pip at run time).

| Tool | Rule | Decision | Reason |
|---|---|---|---|
| trivy | CVE-2026-109518 | fix | apt and libapt-pkg7.0 3.0.3 in the base image; `apt-get upgrade` in the Dockerfile installs the fixed 3.0.4 |
| trivy | CVE-2026-103111 | fix | libpcre2-8-0 10.46-1~deb13u2 in the base image; `apt-get upgrade` installs the fixed 10.46-1~deb13u3 |
| trivy | CVE-2026-84782 | fix | openssl, libssl3t64 and openssl-provider-legacy 3.5.7-1~deb13u2; `apt-get upgrade` installs the fixed deb13u3 |
| trivy | CVE-2026-76844 | fix | zlib1g 1.3.1-1+b1 in the base image; `apt-get upgrade` installs the fixed 1.3.1-1+deb13u1 |
| trivy | CVE-2026-85091 | fix | zlib1g, the same package as the row above, fixed by the same `apt-get upgrade` (1.3.1-1+deb13u1) |
| trivy | GHSA-6q48-6c7w-9gw2 | fix | certifi 2026.7.22 (installed for httpx) and the copy vendored by pip; certifi pinned to 2026.10.23 in requirements.txt, pip removed from the image |
| trivy | CVE-2024-47874 | fix | starlette 0.38.6, pulled in by FastAPI 0.115.0; FastAPI raised to 0.162.7 and starlette pinned to 1.10.0 in requirements.txt |
| trivy | CVE-2026-48818 | fix | starlette 0.38.6 (fixed in 1.1.0); the same FastAPI 0.162.7 / starlette 1.10.0 upgrade in requirements.txt |
| trivy | CVE-2026-54283 | fix | starlette 0.38.6 (fixed in 1.3.1); the same FastAPI 0.162.7 / starlette 1.10.0 upgrade in requirements.txt |
| trivy | GHSA-6v7p-g79w-8964 | fix | msgpack 1.1.2 vendored by pip (`pip/_vendor`), no pip release ships the fix; `pip uninstall -y pip` removes it from the image |
| trivy | CVE-2026-114613 | fix | msgpack 1.1.2 vendored by pip, the same package as the row above; gone with `pip uninstall -y pip` |
| trivy | CVE-2025-47273 | fix | setuptools 70.3.0 (`pkg_resources` vendored by pip); gone with `pip uninstall -y pip` |
| trivy | CVE-2026-97687 | fix | urllib3 2.7.0 vendored by pip (svcdesk's httpx does not use urllib3); gone with `pip uninstall -y pip` |
| trivy | CVE-2026-97689 | fix | urllib3 2.7.0 vendored by pip, the same package as the row above; gone with `pip uninstall -y pip` |
| gitleaks | generic-api-key | ignore | k8s/evidence.json:8072 is the Helm pod annotation `checksum/secret` in my Lab 3 `kubectl get -o json` dump - a SHA-256 of the Grafana chart's Secret, not a secret; fingerprint in .gitleaksignore with this reason (Lab 3 evidence stays unedited) |
| semgrep | dockerfile.security.missing-user.missing-user | accept | Dockerfile:22 (the CMD): svcdesk runs as root in its container. True; accepted until Lab 6 (28.11.2026), where a non-root USER must come together with chown of the /data volume that holds existing SQLite files - changing one without the other breaks writes |
| semgrep | python.lang.security.audit.formatted-sql-query.formatted-sql-query | false-positive | semgrep/rules.py:40 is the deliberate f-string SQL that my own rule svcdesk-sql-query-not-literal must report (`# ruleid:` test case, Stretch 3); the file is never imported or run, svcdesk's src/ has no such query |
| semgrep | python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query | false-positive | semgrep/rules.py:40 and :42, the same two deliberate test cases of my Semgrep rule (f-string and concatenated SQL); svcdesk does not use SQLAlchemy and the test file is never run |

## Bake-off

My canary set (`lab5-canary/`, run 43596388747 on C `90e3b90`, receipt #384) holds 10 labelled defects: 5 in code
(A02 command injection, A04 disabled TLS verification, A08 reset tokens from `random`, A11 `eval` of a formula,
A12 a ticket returned without checking its requester), 3 hard-coded credentials (C01 in `backup.sh`, C02, C06) and
2 vulnerable pins (D01 cryptography, D07 starlette). `bakeoff.json`, per tool:

| tool | TP | FP | FN | precision | recall | F1 |
|---|---|---|---|---|---|---|
| semgrep | 5 | 1 | 5 | 0.8333 | 0.5 | 0.625 |
| gitleaks | 3 | 0 | 7 | 1.0 | 0.3 | 0.4615 |
| trivy | 3 | 0 | 7 | 1.0 | 0.3 | 0.4615 |
| grype | 2 | 0 | 8 | 1.0 | 0.2 | 0.3333 |
| osv-scanner | 2 | 0 | 8 | 1.0 | 0.2 | 0.3333 |

Read per class, every tool is near-perfect inside its own class and blind outside it, so the low recalls are mostly
scope, not quality. gitleaks found all three credentials (3/3) with no false alarm; Trivy's secret scanner found
only C02 and missed `backup.sh` and C06, but Trivy, Grype and OSV-Scanner each found both pins (2/2, precision 1.0).
Semgrep is the only one that reads code: it found three of the five code defects (A02, A04, A11) plus C02 and C06,
and its one FP is the decoy - `jinja2.Environment(autoescape=False)` in `email_render.py`, flagged as XSS, although
the templates render plain-text e-mails where HTML escaping would corrupt them. That is exactly Lecture 5's case:
the rule cannot know the context, only the key can.

What I would put in a gate: gitleaks (every secret, precision 1.0 - one false alarm would teach people to
allow-list) and Trivy fs on dependency files (both pins, precision 1.0, and its findings come with a fixed version
to move to), which is what this pipeline already does. Grype and OSV-Scanner duplicated Trivy's two pins exactly, so
as gates they would add cost and no recall here; they stay as reports. I would not gate on Semgrep `p/default`:
0.83 precision on six results is promising, but on my own service it reported three rules that were an accepted
risk or my own test fixtures, and a gate needs near-zero noise. It belongs in review, where a human decides.

The two defects none of the five found, A08 and A12, have something in common: both are correct-looking code whose
flaw is about *meaning*. `random.choice` is a fine API, wrong only because the result is a password-reset secret
(CWE-338), and `get_ticket_for_customer` is a fine lookup, wrong only because it never compares `ticket.requester`
with `customer` (CWE-639, an IDOR). No pattern says that; a reviewer who knows what the function is for does. So the
union of five scanners reached 8/10, and every recall above is an upper bound: these defects were seeded to be
findable, and seeded defects flatter every detector - on real code I would expect less.
