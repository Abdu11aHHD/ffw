# Verification — 29 October 2026

Verified locally on Windows, Python 3.12 and the bundled Node runtime.

| Check | Result |
|---|---|
| Python/FastAPI pytest suite | 98 passed |
| React integration tests | 8 passed |
| PostgreSQL/PGlite migration and transaction tests | 4 passed |
| TypeScript + Vite production build | passed |
| Actual DeepSeek API on the supplied synthetic PDF | HTTP 200; `source=ai`, provider `deepseek`, model `deepseek-flash` |
| Live HTTP acceptance flow | passed |

The Python suite covers extraction, missing/invalid values, scanned or malformed PDFs, authentication, ownership, deterministic analysis, incompatible period comparison, optional Gemini failure/invalid responses, DeepSeek structured-output validation, fabricated numbers, unknown metric citations, prohibited advice, provider errors, duplicate requests, reviewer authorization, approval/rejection, notifications and report publication only after AI finishes.

The frontend suite checks the team's profile entry, exactly four navigation destinations, in-process mounting, explicit demo login, report history/details, upload validation, waiting for actual processing completion, patient follow-up submission and reviewer gating.

The database tests execute all four migrations against PostgreSQL compiled to WebAssembly, with emulated Supabase auth and Storage schemas. They test patient isolation, denied anonymous reads, service-role-only RPC execution, one appointment per approval, stale-commit rejection and rollback when notification persistence fails. This is local SQL verification, **not a test against a deployed Supabase project**.

The live HTTP acceptance used a synthetic report and a real DeepSeek call. It verified 12 verified metrics, appointment preparation with questions, a submitted follow-up, rejection of a duplicate request, denied patient/anonymous reviewer access, authorized reviewer approval, exactly one simulated appointment, and report/follow-up/decision/appointment notifications without reload duplicates. The DeepSeek source was explicitly `ai`; the local fallback was not counted as AI success. The current demo server contains that synthetic completed workflow.

No test prints an API key or the provider's reasoning content. Automated unit tests force local mode and use MockTransport for provider behavior, so they do not consume the user's API credit. The real API acceptance calls are separate, synthetic-only local checks.

## Remaining boundaries

- Supabase live authentication, private storage and deployment need the owner's project credentials and migration execution. No cloud database was provisioned or connected in this session.
- The team's surrounding shell remains a labelled prototype. Clinical report workflows, appointments and notifications are connected to Python; other shell service tiles and activity illustrations retain their demonstration behavior.
- No OCR, direct sensor/hospital/Sehhaty integration or real booking. Unknown report formats may need user confirmation; detailed episodes cannot be inferred from aggregate percentages.
- English translations of the new report workflow are incomplete; the existing shell language and theme controls remain.
- PDF retention is an explicit maintenance command, not an installed recurring job. Report processing runs in-process; production durability/recovery and an independent clinical/security assessment remain deployment work.
- Structured-output and numeric checks do not establish clinical correctness of every generated sentence.
