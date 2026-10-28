# Privacy, security and limitations

Sukkar Plus is an **independent concept prototype** for an innovation demonstration. It is
not affiliated with Sehhaty, the Saudi Ministry of Health, Insulet, Dexcom or any provider,
and it **does not claim compliance** with any healthcare regulation or security standard.
No regulatory assessment has been carried out.

## What is processed, where

| Data | Demo mode | Live mode |
|------|-----------|-----------|
| Uploaded PDF | Held in process memory for the duration of processing, then dropped | Processed in memory; optionally kept in a **private** Supabase Storage bucket under `<user_id>/<report_id>.pdf`, reachable only through a short-lived signed URL. Set `STORE_REPORT_FILES=false` to keep nothing |
| PDF sent to the AI provider | Never — Gemini is not configured in demo mode | Only when `GEMINI_API_KEY` is set on the server, and only as a cross-check of the printed fields. The call carries the document and nothing else: no name, no user id, no pseudonym |
| Extracted and verified metrics | In-process store, cleared on restart | `sukkar_reports` (owner-only RLS) |
| Name and health number | Synthetic demo values | `patient_identities`, kept separate from analytic tables, which reference the user by UUID only |
| Shared with the reviewer | The snapshot the patient approved: the verified metrics of one report, its period, data-quality notes and a pseudonymous request reference. **Never `user_id`, never a name** | Same |
| Sent to any external automation platform | Nothing. There is none | Nothing. Make.com, n8n and Zapier are explicitly out of scope and no webhook exists |
| Logs | Event names, counts and exception **types** only. No metric values, no file contents, no identifiers | Same |

## Controls implemented

* **Upload validation before parsing**: extension, empty file, 15 MB limit, `%PDF-` header,
  `%%EOF` trailer, encryption dictionary, and a readable-text check that rejects scanned
  documents with an explanation instead of returning an empty result.
* **Secrets server-side only.** The browser bundle never receives the Gemini key or the
  Supabase service-role key. `GET /api/v1/config` reports *whether* something is configured,
  never the value.
* **Row Level Security on every table**, keyed on `auth.uid()`. Roles are stored
  server-side; `profiles` grants `update` on `target_profile` only, so a user cannot make
  themselves a reviewer.
* **Role checks in the API layer, before any privileged client is used.** Frontend
  visibility is never the security boundary: a patient calling a reviewer endpoint directly
  receives 403, and a draft request is 404 for a reviewer.
* **Private report storage** with per-user folder policies and signed URLs.
* **AI grounding guard.** Generated Arabic text is rejected if it contains a number that
  is not traceable to a verified value (after Arabic-Indic digit normalisation), or any
  dosing, medication-change, diagnosis or alarm language. On rejection the deterministic
  template is used and the user is told why.
* **Deletion.** `delete_my_data()` removes every row the caller owns, across reports,
  notifications, follow-ups, appointments, labs, consents and identity.
* **Retention.** `REPORT_RETENTION_DAYS` (default 180) documents how long stored report
  files are intended to be kept. Enforcement is a scheduled job you must add for a real
  deployment; the prototype does not run one.

## Clinical limitations

* **No diagnosis, no emergency triage, no treatment or dose advice.** The urgent-concern
  path shows general safety messaging and points to emergency services; it never waits for
  a reviewer and never assesses whether a situation is urgent.
* All review-trigger rules are **demonstration rules** (see `SOURCE_MAPPING.md`). Using a
  published population-level reference target as a trigger for a review task is a design
  choice for this prototype, not a validated clinical triage criterion.
* **"ملخص روتيني للموعد" is never a statement of safety.** It means no configured rule
  fired on the available verified data.
* General consensus targets are population-level and are shown only for the population the
  user selects. Pregnancy and paediatric targets are deliberately **not** applied.
* Printed PDF summaries cannot support episode detection or time-of-day pattern analysis.
  The app says so rather than reconstructing a time series it does not have.
* The Omnipod Discover summary layout is the only **verified** format. Other AGP-style
  reports are parsed best-effort and every value must be confirmed individually.
* **The reviewer is not a clinician.** Requests never reach a healthcare provider.
  Appointments created after a decision are flagged `is_simulated` in the database and
  labelled as prototype appointments in every response and on every screen. **No real
  appointment is ever booked, and there is no integration with Sehhaty or any hospital
  system.**

## Data used to build and test

* **Synthetic data only** in this repository: the demo patient, the demo reviewer and a
  synthetic report rendered in the supported layout.
* The real Omnipod report supplied during development was used locally to verify the
  parser's layout handling and is **not** included. Personal details on it (name, date of
  birth, device serial) were never written to any project file, and the parser is written
  so that those fields are never read into a value.

## Before sending real health data anywhere

* Review Google's current Gemini API terms for your account tier — data-use terms differ
  between unpaid and paid usage. The default configuration sends nothing, because no key
  is set.
* Carry out a proper privacy and security assessment against the regulations that apply to
  you. This prototype has not had one, and nothing in it should be read as a claim that it
  has.
