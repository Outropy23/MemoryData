# Security Policy — MemoryData

## Repository Owner

**Outropy23** — https://github.com/Outropy23
ItalyWorld R&D

## Reporting Security Issues

If you discover a security vulnerability in this repository, please report it privately:
- Open a GitHub Security Advisory: https://github.com/Outropy23/MemoryData/security/advisories/new
- Do NOT open a public issue for security vulnerabilities.

## Unauthorized Access Policy

This repository does not accept unsigned or unverified contributions from unknown parties.
All commits must be authorized by the repository owner (Outropy23).

Any `Co-authored-by` attributions in commit messages that reference identities not
authorized by Outropy23 are considered unauthorized and should be reported.

## Commit Signing

Future commits to this repository will be signed using GPG or Sigstore/COSIGN.
To verify commit authenticity:

```bash
# Verify GPG-signed commits
git log --show-signature

# Verify with cosign (when enabled)
cosign verify-blob --key cosign.pub <file>
```

## Known Unauthorized Attribution Attempt

Commits on branch `feat/adam-gothamv3-swarm64` (SHA: b674a2a, 3549b6a) contain
`Co-authored-by: italy@ilmondo-rd.com` — this attribution was NOT authorized by the
repository owner and does not reflect genuine co-authorship.

---
Last updated: 2026-08-18
