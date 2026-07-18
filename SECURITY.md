# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. Thank you for improving the security of
WildfireFrontDynamics. We encourage responsible disclosure.

### Please DO NOT open public GitHub issues for security vulnerabilities.

Instead, please report them **privately** via GitHub’s built-in private
vulnerability reporting (no public security email is published yet):

1. Open the repository on GitHub → **Security** tab → **Report a vulnerability**
2. Or use the direct advisory form if enabled for this repo:
   `https://github.com/AlonsoAlviraa/WildfireFrontDynamics/security/advisories/new`

> **Note:** A dedicated security contact email may be added later. Until then,
> GitHub private vulnerability reporting is the **only** supported channel.
> Do not invent or use placeholder addresses such as `security@example.org`.

3. **Include** (if possible):
   - Description of the vulnerability and its impact
   - Steps to reproduce or proof-of-concept
   - Affected versions/commit hashes
   - Suggested mitigation or fix

### Response timeline

| Step                  | Target SLA  |
| --------------------- | ----------- |
| Acknowledge report    | ≤ 48 hours  |
| Initial assessment    | ≤ 7 days    |
| Fix or mitigation     | ≤ 30 days   |

We will keep you informed of progress and credit you in the advisory (unless you
prefer to remain anonymous).

## Security measures in this project

- **SHA-256 provenance**: Every ingested frame is hashed and recorded in the
  manifest, ensuring traceability and tamper detection.
- **Leak-free pipeline**: Strict separation of `observed`, `inferred`, and
  ground-truth (`GT`) data prevents train/test contamination.
- **Non-root Docker container**: The runtime image runs as an unprivileged user.
- **Pinned dependencies**: Core dependencies use lower-bound version pins to
  receive security patches.
- **Safe model loads**:
  - PyTorch checkpoints use `torch.load(..., weights_only=True)` where possible.
  - Meta-Labeler serialization prefers **joblib** + JSON metadata, but **joblib
    is not RCE-safe** (it uses pickle under the hood for sklearn objects).
    Both joblib and pickle loads are restricted to allowlisted roots
    (default: `models/`). Renaming `.pkl` → `.joblib` does not bypass the gate.
    Pass `allowlisted_roots` only for trusted directories. Treat model files as
    untrusted input unless their provenance is known.

## Dependency scanning

This project is scanned automatically via:

- **GitHub Dependabot** (enabled in `.github/dependabot.yml`)
- **CodeQL** (optional workflow in `.github/workflows/codeql.yml` — enable
  GitHub Advanced Security / Code scanning in repo settings if available on
  your plan; otherwise treat CodeQL as a future hardening step)

Results appear in the **Security** tab under **Dependency advisories** and,
when CodeQL is enabled, **Code scanning alerts**.

## Data handling

This project processes geospatial wildfire imagery. No personally identifiable
information (PII) is handled. Raw data is stored locally and is **never**
uploaded to external services unless explicitly configured by the operator
(e.g., Kaggle training jobs).
