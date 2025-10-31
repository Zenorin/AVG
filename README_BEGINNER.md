# DirectorOS Actions API — Beginner Runbook (v0.3.1a)


This is a small FastAPI server that exposes 4 endpoints used by a strict Custom GPT orchestrator. It encodes shot-centric, Sora-aligned prompting rules and a deterministic QA stage.


## 1) Local Quickstart
```bash
python -m venv .venv
source .venv/bin/activate # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env # then edit ACTIONS_BEARER
uvicorn app:app --host 0.0.0.0 --port 8000