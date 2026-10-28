# Adheed integration status

The original integration boundary is now connected through `mount.ts` to `src/adheed/AdheedFeature.tsx`. It runs in the same React router, with no iframe. The existing team header, profile tile, language/theme controls and four bottom navigation destinations remain.

Sub-routes: upload, reports, reports/:id, visit-prep, visit-prep/:reportId, followups, followups/new, followups/:id and how-it-works. `/reviewer` is a separate role-protected UI outside the mobile shell. `/appointments` and `/notifications` use the authenticated Python API. The feature API session is independent of the fictional profile switcher.

The report workflow is Arabic-first. The shell retains its existing Arabic/English support. See the root README for setup and explicit limitations.
