# Security Policy — MemoryData

## Repository Owner

**Cesare Semovigo (Outropy23)** — https://github.com/Outropy23
ItalyWorld R&D

This repository is the exclusive property of Cesare Semovigo. All intellectual property,
source code, architecture, and patent disclosures belong solely to the owner.

---

## Contribution Rules

1. **No external contributions accepted.** This is a private research repository. Pull requests
   from unknown or unauthorized parties will be closed without review.
2. **All commits must be explicitly authorized** by Cesare Semovigo (Outropy23).
3. **No AI agent may be listed as author or co-author** without explicit written approval
   from the repository owner.
4. **Co-authored-by attributions** not authorized by the owner are invalid and must be
   reported immediately via GitHub Security Advisory.
5. **No forking for redistribution** without written permission from the owner.

---

## Unauthorized Access Policy

Any contribution, commit, fork, or attribution that has not been explicitly authorized
by Cesare Semovigo (Outropy23) is considered unauthorized and will be:
- Reported to GitHub Trust & Safety
- Documented in this file as a security incident
- Subject to DMCA takedown if applicable

---

## Reporting Security Issues

If you discover a security vulnerability in this repository, please report it privately:
- Open a GitHub Security Advisory: https://github.com/Outropy23/MemoryData/security/advisories/new
- Do **NOT** open a public issue for security vulnerabilities.
- Do **NOT** disclose publicly before the owner has been notified and has responded.

---

## Commit Signing

All authorized commits to this repository are signed.
To verify commit authenticity:

```bash
# Verify GPG-signed commits
git log --show-signature

# Verify with cosign (when enabled)
cosign verify-blob --key cosign.pub <file>
```

---

## Known Unauthorized Attribution

Commits on branch `feat/adam-gothamv3-swarm64` (SHA: b674a2a, 3549b6a) contain
`Co-authored-by: italy@ilmondo-rd.com` — this attribution was **NOT** authorized by the
repository owner and does not reflect genuine co-authorship.

---
Last updated: 2026-08-18
