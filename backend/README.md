# عضيد — FastAPI backend

See the root README for setup and the complete demo. From this directory, create a Python 3.12 virtualenv, install `requirements-dev.txt`, copy `.env.example` to `.env`, and run:

    python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
    python -m pytest

`AI_PROVIDER=deepseek` selects grounded Arabic interpretation with `deepseek-flash`. The key stays in the ignored backend `.env`. Optional providers are `gemini` and `local`. Missing or rejected AI output is labelled as a deterministic Python summary. Demo data is held in memory and lost on restart. Live Supabase requires all four migrations and explicit configuration.
