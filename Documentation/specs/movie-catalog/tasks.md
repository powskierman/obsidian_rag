# Tasks: Movie Catalog Subsystem

Tasks ID: `OC-TASKS-MOVIES-v1.0.0`
Spec: `OC-SPEC-MOVIES-v1.0.0`
Plan: `OC-PLAN-MOVIES-v1.0.0`

## Foundation

- [x] Create a dedicated movie subsystem branch
- [x] Define doc placement inside `Documentation/`
- [x] Add canonical schema and storage bootstrap

## Ingestion

- [x] Implement Apple CSV parsing
- [x] Implement NAS TXT parsing
- [x] Normalize both into a shared staging model
- [x] Preserve raw provenance

## Matching and Resolution

- [x] Add title normalization helpers
- [x] Add year extraction helpers
- [x] Add alternate-cut markers
- [x] Merge straightforward duplicate ownership cases
- [x] Keep ambiguous title-only cases in manual review

## Enrichment

- [x] Define metadata provider abstraction
- [x] Add null provider
- [x] Add optional OMDb-backed provider with cache

## Obsidian Projection

- [x] Define frontmatter contract
- [x] Add note template
- [x] Generate `Media/Movies/*.md`
- [x] Preserve a user-editable notes block

## Reporting

- [x] Generate unresolved match report
- [x] Generate summary report

## Verification

- [x] Add unit tests for normalization and matching
- [x] Add integration test for end-to-end pipeline
- [x] Verify idempotent reruns in integration coverage
