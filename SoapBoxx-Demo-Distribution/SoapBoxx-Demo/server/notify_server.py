#!/usr/bin/env python3
"""
Minimal FastAPI server: POST /notify with JSON body, forwards email to admin via SMTP or Resend.

Deploy (example):
  pip install -r requirements.txt
  export SMTP_HOST=smtp.gmail.com SMTP_PORT=587 SMTP_USER=... SMTP_PASSWORD=...
  export MAIL_TO=recipient@example.com MAIL_FROM=your-sender@gmail.com ...
  uvicorn notify_server:app --host 0.0.0.0 --port 8080

Then in the desktop app .env:
  NOTIFY_WEBHOOK_URL=https://your-host/notify
"""

import os
import sys
from pathlib import Path

# Allow importing notify_client from parent/backend
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "backend"))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional

app = FastAPI(title="SoapBoxx Notify")


class NotifyBody(BaseModel):
    event: str
    user_id: str
    detail: Optional[Dict[str, Any]] = None


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/notify")
def notify(body: NotifyBody):
    try:
        from notify_client import notify_admin_sync

        notify_admin_sync(body.event, body.user_id, body.detail)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
