import os
import io
import csv
import hmac
import hashlib
import secrets
import time
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import razorpay

import db

load_dotenv()

db.init_db()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

app = FastAPI(title="Stall Payments")


# ---------- helpers ----------
def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_readable_key() -> str:
    part = lambda: secrets.token_hex(3).upper()
    return f"STALL-{part()}-{part()}"


def check_admin(x_admin_password: Optional[str]):
    if x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_stall_from_token(x_stall_token: Optional[str]):
    if not x_stall_token:
        raise HTTPException(status_code=401, detail="Missing stall token")
    stall = db.get_stall_by_token(x_stall_token)
    if not stall:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return stall


# ---------- request bodies ----------
class CreateStallBody(BaseModel):
    stallName: str


class LoginBody(BaseModel):
    key: str


class PaymentBody(BaseModel):
    amount: float
    description: Optional[str] = ""


# ---------- ADMIN ----------
@app.post("/api/admin/stalls")
def create_stall(body: CreateStallBody, x_admin_password: Optional[str] = Header(None)):
    check_admin(x_admin_password)
    stall_name = body.stallName.strip()
    if not stall_name:
        raise HTTPException(status_code=400, detail="stallName is required")

    key = generate_readable_key()
    stall_id = db.create_stall(stall_name, hash_key(key))
    return {"id": stall_id, "stallName": stall_name, "key": key}


@app.get("/api/admin/stalls")
def list_stalls(x_admin_password: Optional[str] = Header(None)):
    check_admin(x_admin_password)
    return db.list_stalls()


@app.get("/api/admin/dashboard")
def admin_dashboard(x_admin_password: Optional[str] = Header(None)):
    check_admin(x_admin_password)
    return {
        "stalls": db.list_stalls(),
        "payments": db.list_payments_with_stall(),
    }


@app.get("/api/admin/export.csv")
def export_csv(x_admin_password: Optional[str] = Header(None)):
    check_admin(x_admin_password)
    rows = db.list_payments_with_stall()

    buffer = io.StringIO()
    fieldnames = ["payment_id", "stall_id", "stall_name", "amount_inr", "description", "status", "created_at", "paid_at"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=payments.csv"},
    )


# ---------- STALL ----------
@app.post("/api/stall/login")
def stall_login(body: LoginBody):
    key = body.key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="key is required")

    stall = db.get_stall_by_key_hash(hash_key(key))
    if not stall:
        raise HTTPException(status_code=401, detail="Invalid key")

    token = secrets.token_hex(24)
    db.set_stall_token(stall["id"], token)
    return {"token": token, "stallName": stall["stall_name"]}


@app.post("/api/stall/payment")
def create_payment(body: PaymentBody, x_stall_token: Optional[str] = Header(None)):
    stall = get_stall_from_token(x_stall_token)

    if not body.amount or body.amount <= 0:
        raise HTTPException(status_code=400, detail="Valid amount is required")

    try:
        qr = rzp_client.qrcode.create({
            "type": "upi_qr",
            "name": stall["stall_name"],
            "usage": "single_use",
            "fixed_amount": True,
            "payment_amount": round(body.amount * 100),  # paise
            "description": body.description or f"Payment to {stall['stall_name']}",
            "close_by": int(time.time()) + 15 * 60,  # 15 min expiry
            "notes": {"stall_id": str(stall["id"])},
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create QR code: {e}")

    payment_id = db.create_payment(
        stall_id=stall["id"],
        qr_code_id=qr["id"],
        amount_inr=body.amount,
        description=body.description or "",
    )

    return {
        "paymentId": payment_id,
        "qrCodeId": qr["id"],
        "qrImageUrl": qr["image_url"],
        "amount": body.amount,
    }


@app.get("/api/stall/payment/{payment_id}/status")
def payment_status(payment_id: int, x_stall_token: Optional[str] = Header(None)):
    stall = get_stall_from_token(x_stall_token)

    payment = db.get_payment(payment_id)
    if not payment or payment["stall_id"] != stall["id"]:
        raise HTTPException(status_code=404, detail="Not found")

    if payment["status"] == "paid":
        return {"status": "paid"}

    try:
        result = rzp_client.qrcode.payments(payment["qr_code_id"])
        if result.get("items"):
            db.mark_payment_paid(payment_id)
            return {"status": "paid"}
    except Exception:
        pass

    return {"status": "pending"}


# ---------- WEBHOOK ----------
@app.post("/api/webhook/razorpay")
async def razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")

    expected = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=400, detail="Invalid signature")

    import json
    event = json.loads(body)

    if event.get("event") == "qr_code.credited":
        qr_code_id = event["payload"]["qr_code"]["entity"]["id"]
        payment = db.get_payment_by_qr_code_id(qr_code_id)
        if payment:
            db.mark_payment_paid(payment["id"])

    return {"status": "ok"}


# ---------- static frontend (mounted last so it doesn't shadow /api routes) ----------
@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse(url="/index.html")


app.mount("/", StaticFiles(directory="public", html=True), name="public")
