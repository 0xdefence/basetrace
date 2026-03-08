import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services.db import get_conn

router = APIRouter()


class WaitlistIn(BaseModel):
    email: str
    source: str = "alpha_page"


@router.post('/waitlist')
def waitlist_signup(body: WaitlistIn):
    email = body.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="invalid_email")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO waitlist_signups(email, source)
            VALUES(%s,%s)
            ON CONFLICT(email) DO NOTHING
            RETURNING id, email, source, created_at
            """,
            (email, body.source),
        )
        row = cur.fetchone()
        if row:
            i, email, source, created = row
            return {"ok": True, "signup": {"id": int(i), "email": email, "source": source, "created_at": created.isoformat() if created else None}}

        cur.execute("SELECT id, email, source, created_at FROM waitlist_signups WHERE email=%s", (email,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=500, detail="waitlist_insert_failed")
        i, email, source, created = row
        return {"ok": True, "existing": True, "signup": {"id": int(i), "email": email, "source": source, "created_at": created.isoformat() if created else None}}


@router.get('/waitlist/stats')
def waitlist_stats():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM waitlist_signups")
        total = int(cur.fetchone()[0] or 0)
    return {"ok": True, "waitlist_signups": total}
