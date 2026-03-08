import os
from typing import Any, Dict

import httpx


def _format_message(alert: Dict[str, Any]) -> str:
    a_type = alert.get("type", "unknown")
    address = alert.get("address", "-")
    severity = alert.get("severity", "medium")
    confidence = alert.get("confidence", 0)
    evidence = alert.get("evidence", {}) or {}
    return (
        f"BaseTrace alert: {a_type}\n"
        f"severity={severity} confidence={confidence}\n"
        f"address={address}\n"
        f"evidence={evidence}"
    )


def send_discord(alert: dict):
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook:
        return {"ok": False, "channel": "discord", "error": "missing_discord_webhook"}

    body = {"content": _format_message(alert)}
    try:
        r = httpx.post(webhook, json=body, timeout=8.0)
        if r.status_code >= 400:
            return {
                "ok": False,
                "channel": "discord",
                "status_code": r.status_code,
                "error": r.text[:250],
                "destination": webhook,
            }
        return {"ok": True, "channel": "discord", "status_code": r.status_code, "destination": webhook}
    except Exception as e:
        return {"ok": False, "channel": "discord", "error": str(e), "destination": webhook}


def send_telegram(alert: dict):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return {"ok": False, "channel": "telegram", "error": "missing_telegram_token_or_chat"}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = {"chat_id": chat_id, "text": _format_message(alert), "disable_web_page_preview": True}
    try:
        r = httpx.post(url, json=body, timeout=8.0)
        if r.status_code >= 400:
            return {
                "ok": False,
                "channel": "telegram",
                "status_code": r.status_code,
                "error": r.text[:250],
                "destination": chat_id,
            }
        data = r.json() if r.content else {}
        return {
            "ok": bool(data.get("ok", True)),
            "channel": "telegram",
            "status_code": r.status_code,
            "destination": chat_id,
        }
    except Exception as e:
        return {"ok": False, "channel": "telegram", "error": str(e), "destination": chat_id}
