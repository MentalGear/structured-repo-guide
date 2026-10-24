---
id: 2
title: "Evict the fragment cache by size"
status: open
area: cache
updated: 2025-01-15
---

# Item 2: evict the fragment cache by size

## Item

The cache is dropped at the end of a request only. A long request can grow it without bound.

## Status

Not started.

## Detail

Option A: a size cap with least-recently-used eviction. Option B: a per-key time limit. A is simpler.
