---
name: ralph
description: >-
  Autonomous PRD and task execution loop with programmatic backpressure.
  Iterates over specifications until all acceptance criteria pass without context degradation.
---

# Ralph: Autonomous Task Execution Loop

## Purpose
The Ralph methodology ensures relentless, test-backed execution against a Product Requirements Document (PRD) or architectural task list. Ralph loops through tasks, relying on filesystem state and automated test backpressure.

## Core Rules
1. **Source of Truth**: The task list or PRD file on disk (`docs/PLAN.md` or equivalent) represents project state.
2. **Programmatic Backpressure**: A task is NOT done until tests pass. If tests fail, diagnose and fix immediately.
3. **Context Freshness**: Avoid accumulating megabytes of conversation history; store persistent findings, diffs, and decisions in documentation files on disk.
4. **Idempotence**: Every step can be resumed or re-run cleanly from disk state.
