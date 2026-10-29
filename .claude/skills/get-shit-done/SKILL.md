---
name: get-shit-done
description: >-
  Disciplined meta-prompting, context engineering, and spec-driven execution framework.
  Combats agent context rot through phased execution: Discuss -> Plan -> Execute -> Verify -> Ship.
---

# Get Shit Done (GSD) Framework

## Purpose
The GSD skill enforces structured, spec-driven development. It prevents "context rot" and "vibecoding" by breaking large software projects into strict, verifiable phases with atomic commits and fresh-context execution.

## Core Phases
1. **Discuss**: Align on goals, edge cases, external contracts, and non-negotiables before creating files.
2. **Plan**: Decompose the task into discrete, sequentially dependent milestones with clear acceptance criteria.
3. **Execute**: Build in parallel waves where independent, writing atomic, production-grade code.
4. **Verify**: Apply programmatic backpressure: run linter, typecheck, unit tests, and integration tests.
5. **Ship**: Package the changes, update documentation, and report verifiable deliverables.

## Operational Rules
- Never jump into writing application code without an approved architectural plan.
- Keep the main context window lean by delegating deep sub-tasks or research to isolated subagents or scripts.
- Validate every state transition against automated test output.
