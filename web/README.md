# Adheed frontend

The team shell is preserved. The feature is now mounted in-process at `/my-profile/diabetes-journey/*` and connects to FastAPI. Report processing, follow-ups, reviewer decisions, appointments and notifications are backend-driven. See the root README for complete setup, authentication, demo workflow and limitations.

Run `npm install` then `npm run dev` (port 5174). The development proxy forwards `/api` to port 8001. Run `npm test` and `npm run build` for verification. `src/adheed` is the feature boundary; utility styles are scoped to avoid altering the team shell.
