#!/usr/bin/env python3
"""
Merkle Chain - Tamper-Evidence Engine
FIPS 202 SHA-3 leaf hashing | NIST SP800-208 chain construction
ItalyWorld R&D / Cesare Semovigo
"""

import hashlib
import json
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class MerkleLeaf:
    index: int
    data_hash: str
    chain_hash: str


class MerkleChain:
    """
    Sequential (non-tree) Merkle chain:
        chain[i] = SHA3-256( chain[i-1] || SHA3-256(data[i]) )
    Provides:
      - append-only insertion
      - O(n) full verification
      - WORM-compatible (no deletion)
    """

    def __init__(self, genesis_hash: Optional[str] = None):
        self._head = genesis_hash or "0" * 64
        self._leaves: List[MerkleLeaf] = []

    def append(self, data: dict) -> MerkleLeaf:
        serialized = json.dumps(data, sort_keys=True, default=str).encode()
        leaf_hash = hashlib.sha3_256(serialized).hexdigest()
        chain_hash = hashlib.sha3_256((self._head + leaf_hash).encode()).hexdigest()
        self._head = chain_hash
        leaf = MerkleLeaf(index=len(self._leaves), data_hash=leaf_hash, chain_hash=chain_hash)
        self._leaves.append(leaf)
        return leaf

    def verify(self) -> bool:
        head = "0" * 64
        for leaf in self._leaves:
            expected = hashlib.sha3_256((head + leaf.data_hash).encode()).hexdigest()
            if expected != leaf.chain_hash:
                return False
            head = leaf.chain_hash
        return head == self._head

    @property
    def head(self) -> str:
        return self._head

    @property
    def length(self) -> int:
        return len(self._leaves)
