---
id: 1
title: "Cache key includes the locale"
status: done
area: cache
updated: 2025-01-14
---

# Item 1: cache key includes the locale

## Item

Two locales can render the same fragment id to different text, so the cache key must name the locale.

## Status

Landed in commit 3fa9c21 (2025-01-14). Before it, a German page could show the English fragment that an earlier
request had cached; an outage on 2025-01-13 was this bug.

## Detail

The incident story belongs here and nowhere else. The code comment says only why the key is shaped as it is and
cites "backlog 1". The round's landing log is
[archived](../../archive/rounds/round-1-landing-log.md).
