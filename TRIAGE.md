---
lab5_triage:
  image: ghcr.io/TODO-owner/TODO-repo@sha256:TODO           # the digest the image job printed on main, lower case (P-10)
  sarif_receipt: 0                                         # the issue number of your SARIF receipt (P-10)
---
<!-- ai-generated: 90% - Claude Code (Opus 5.5) ran the scanners locally and in CI, made the fixes and drafted the rows; I reviewed them -->
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

## Bake-off

TODO (at least 600 characters, P-13).
