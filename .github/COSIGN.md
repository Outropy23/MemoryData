# Commit & Release Signing — COSIGN Setup

## Owner: Outropy23 / MemoryData

This document describes how to enable Sigstore COSIGN signing for this repository.

## Install cosign

```bash
# macOS
brew install sigstore/tap/cosign

# Linux
curl -O -L "https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64"
chmod +x cosign-linux-amd64
sudo mv cosign-linux-amd64 /usr/local/bin/cosign
```

## Generate a key pair (run once, keep private key safe)

```bash
cosign generate-key-pair
# Creates: cosign.key (PRIVATE — never commit) and cosign.pub (public — commit this)
```

## Sign a file or release artifact

```bash
cosign sign-blob --key cosign.key --output-signature artifact.sig artifact.tar.gz
```

## Verify a signed artifact

```bash
cosign verify-blob --key cosign.pub --signature artifact.sig artifact.tar.gz
```

## Enable Gitsign for commit signing (Sigstore keyless)

```bash
# Install gitsign
go install github.com/sigstore/gitsign@latest

# Configure git to use gitsign
git config --global gpg.x509.program gitsign
git config --global gpg.format x509
git config --global commit.gpgsign true
```

## Verify a commit signature

```bash
git verify-commit HEAD
```

---
Repository owner: Outropy23
Date: 2026-08-18
