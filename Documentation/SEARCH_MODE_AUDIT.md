# Search Mode Audit Report

**Date:** 2026-01-23 14:32:53
**Query used:** `What is the treatment for DLBCL?`

| Mode | Status | Duration | Answer Len | Sources | Details |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **vector** | PASS | 0.79s | 14 | 10 | OK |
| **notes** | PASS | 3.97s | 601 | 0 | OK |
| **entities** | PASS | 0.88s | 1184 | 0 | OK |
| **notes+vector** | PASS | 5.56s | 686 | 0 | OK |
| **entities+vector** | PASS | 0.93s | 0 | 0 | OK |
| **dual-graph** | PASS | 4.22s | 537 | 0 | OK |
| **hybrid** | PASS | 6.22s | 647 | 0 | OK |
| **cascading** | PASS | 7.35s | 526 | 7 | OK |
| **deep-thinking** | PASS | 73.11s | Streamed | N/A | Received 36 chunks. Final Answer: False |
