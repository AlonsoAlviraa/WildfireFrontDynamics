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

Instead, please report them **privately**:

1. **Email**: Send a description to the maintainers via GitHub's private
   vulnerability reporting:
   - Go to the **Security** tab → **Report a vulnerability**
   - Or email: `security@example.org` (replace with real contact)

2. **Include** (if possible):
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

## Dependency scanning

This project is scanned automatically via:

- **GitHub Dependabot** (enabled in `.github/dependabot.yml`)
- **CodeQL** analysis (if enabled in repo settings)

Results appear in the **Security** tab under **Dependency advisories**.

## Data handling

This project processes geospatial wildfire imagery. No personally identifiable
information (PII) is handled. Raw data is stored locally and is **never**
uploaded to external services unless explicitly configured by the operator
(e.g., Kaggle training jobs).