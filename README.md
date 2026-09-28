# Stall Payments (FastAPI version)

Same app as before, rebuilt with Python + FastAPI instead of Node.js. Plain HTML/CSS frontend, no build step.

## 1. Install Python (if you don't have it)

Download from python.org (3.10 or newer) and install. On the installer's first screen, **check the box "Add Python to PATH"** before clicking Install — this step is easy to miss and causes most setup problems.

Verify it worked — open a terminal in the project folder and run:
```
python --version
```

## 2. Set up a virtual environment

This keeps this project's Python packages separate from everything else on your machine.

```
python -m venv venv
```

Activate it:
- **Windows (PowerShell):** `venv\Scripts\Activate.ps1`
- **Windows (cmd.exe):** `venv\Scripts\activate.bat`
- **Mac/Linux:** `source venv/bin/activate`

You'll know it worked because your terminal prompt now starts with `(venv)`. You need to activate it every time you open a new terminal to work on this.

## 3. Install dependencies

```
pip install -r requirements.txt
```

## 4. Configure your keys

```
copy .env.example .env
```
(Mac/Linux: `cp .env.example .env`)

Open `.env` in Notepad and fill in:
- `ADMIN_PASSWORD` — make one up
- `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` — from Razorpay Dashboard → Settings → API Keys (use `rzp_test_...` keys to test first, real `rzp_live_...` keys for the actual event)
- `RAZORPAY_WEBHOOK_SECRET` — set this up later, see step 6

The app reads `.env`, not `.env.example`. If you have not copied the example to `.env`, local development falls back to the password `changeme`.

## 5. Run it

```
py -m uvicorn main:app --reload --reload-exclude .venv
```

You should see `Uvicorn running on http://127.0.0.1:8000`. Open `http://127.0.0.1:8000/` for the home page, then choose:
- **Stall owner** — sign in with a stall key, create a payment QR, and watch its status
- **Organizer** — add stalls, review payments across the event, and export CSV

`--reload` restarts the server automatically if you edit the code. Drop it for the real event (slightly more stable without it).

## 6. Set up the Razorpay webhook (for reliability at the event)

The stall page also polls every 3 seconds as a fallback, but the webhook confirms payment instantly.

In Razorpay Dashboard → Settings → Webhooks:
- URL: `https://your-deployed-domain.com/api/webhook/razorpay`
- Event: `qr_code.credited`
- Set a webhook secret, put the same value into `.env` as `RAZORPAY_WEBHOOK_SECRET`

## 7. Deploy for the real event

`127.0.0.1` / `localhost` only works on your own machine — stall owners on their own phones can't reach it. Deploy to a real server with HTTPS:
- **Render** or **Railway**: connect this folder as a repo, set env vars in their dashboard, they auto-detect Python and can run `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **A VPS**: install Python, repeat steps 2–4 there, run with something like `pm2` or a `systemd` service so it survives reboots, put behind nginx with HTTPS

## Git and secrets

The `.gitignore` excludes local credentials, virtual environments, Python cache files, and the SQLite database. Commit `.env.example` as a template, but never commit `.env` or real Razorpay credentials. Replace every placeholder in `.env.example` after copying it to `.env`.

## What this does and doesn't cover

- Stall keys are stored as SHA-256 hashes, not plaintext
- Data is stored in `data.sqlite` (Python's built-in SQLite — no extra install needed)
- QR codes expire after 15 minutes — change `close_by` in `main.py` if you want a different window
- No refund flow — this only tracks payments in
