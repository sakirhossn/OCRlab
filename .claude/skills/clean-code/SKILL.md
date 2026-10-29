---
name: clean-code
description: >-
  Clean architecture, SOLID design, idiomatic typing, readable code, and rigorous testing standards.
---

# Clean Code and Architecture Standards

## Principles
1. **Explicit is Better than Implicit**: Use explicit type annotations (Python `typing`, Pydantic v2 schemas, TypeScript interfaces). No untyped `Any` or `dict` blobs in API contracts.
2. **Single Responsibility**: Each module, class, and function has one well-defined purpose:
   - `services/pdf_validator.py` only validates PDFs.
   - `services/lease_manager.py` only handles worker lease timing and states.
   - `services/webhook_dispatcher.py` only handles HMAC signatures and SSRF-safe delivery.
3. **Fail Fast & Explicitly**: Validate all inputs at system boundaries using RFC-compliant error responses.
4. **Idempotence & Graceful Recovery**: All worker completions, webhook deliveries, and document deletions must be safe to retry.
5. **Self-Documenting Code**: Clear function names, concise docstrings for complex algorithms, and no commented-out zombie code.
