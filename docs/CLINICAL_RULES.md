# Reference rules and limits

The retained Python target tables reference Battelino et al., *Clinical Targets for Continuous Glucose Monitoring Data Interpretation*, Diabetes Care 2019;42:1593–1603, tables 2–3. Primary source: https://diabetesjournals.org/care/article/42/8/1593/36184/Clinical-Targets-for-Continuous-Glucose-Monitoring

The general-adult reference includes a 14-day observation recommendation, 70% active data, TIR >70%, TBR <70 mg/dL <4%, TBR <54 mg/dL <1%, TAR >180 mg/dL <25%, TAR >250 mg/dL <5%, CV ≤36%. These are population reference goals, not personal prescriptions. Distinct profiles and insufficient-data states are retained in Python. No target set is silently applied to pregnancy, children or unspecified profiles.

Using reference-goal deviations to offer a prototype review request is a product rule, **not a validated triage rule**. An aggregate PDF does not establish the timing, duration or cause of individual episodes. Detailed episode rules are not applicable without timed readings. Missing metrics do not become zero. The early-warning and clinical effectiveness of this prototype have not been validated.

DeepSeek receives only verified metrics, duration, deterministic outcome and supplied rule evidence. Its prose cannot alter the stored values or workflow decision. The API validates JSON shape, metric references, numbers and prohibited wording; these checks cannot prove every clinical statement correct. Clinician review remains simulated in this prototype.

Provider references used for the integration:
- https://api-docs.deepseek.com/quick_start/pricing
- https://api-docs.deepseek.com/guides/thinking_mode/
- https://github.com/googleapis/python-genai
