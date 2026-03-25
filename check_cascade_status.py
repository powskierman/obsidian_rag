#!/usr/bin/env python3
"""Check cascading query status from API response."""
import json
import sys

data = json.load(sys.stdin)

print('=== SYNTHESIS STATUS ===')
print(f"Fallback reason: {data.get('results', {}).get('synthesis_fallback_reason', 'none')}")
print(f"Answer length: {len(data.get('answer', ''))} chars")

print('\n=== STAGE STATUSES ===')
diag = data.get('results', {}).get('diagnostics', {})
for stage, status in diag.get('statuses', {}).items():
    print(f"{stage}: {status}")

print('\n=== FAILURES ===')
failures = diag.get('failures', {})
if failures:
    for stage, error in failures.items():
        print(f"  {stage}: {error}")
else:
    print("  None")

print('\n=== WARNINGS ===')
warnings = data.get('metadata', {}).get('warnings', [])
if warnings:
    for w in warnings:
        print(f"⚠️  {w}")
else:
    print("  None")

print('\n=== ANSWER PREVIEW ===')
answer = data.get('answer', '')
print(answer[:500] + ('...' if len(answer) > 500 else ''))
