# Stall Payments

A small self-hosted system for events with multiple stalls:
- You generate a one-time key per stall (from the admin page)
- Stall owner logs in with that key
- They enter an amount + description → a Razorpay UPI QR appears for that exact amount
- Every stall + payment (amount, description, status, timestamps) is logged
- You export it all as CSV from the admin page

## 1. Local setup

```bash
npm install
cp .env.example .env
```

Fill in `.env`:
- `ADMIN_PASSWORD` — pick a strong password (this guards the admin page)
- `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` — from your Razorpay dashboard → Settings → API Keys
- `RAZORPAY_WEBHOOK_SECRET` — see step 3 below

Run it:
```bash
npm start
```
Visit `http://localhost:3000/admin.html` and `http://localhost:3000/stall.html`.

## 2. Generate stall keys

On `/admin.html`, enter your admin password, type a stall name, click **Generate Key**.
The key is shown **once** — copy it and hand it to that stall owner (write it down, screenshot, whatever works for your event). It's not stored anywhere in plaintext, only its hash, so if it's lost you just generate a new one for that stall.

## 3. Set up the Razorpay webhook (important for reliability)

The app polls Razorpay every 3 seconds as a fallback, but a webhook is the reliable way to catch payment confirmation instantly, especially under bad network conditions at a live event.

In your Razorpay Dashboard → Settings → Webhooks:
- Webhook URL: `https://your-deployed-domain.com/api/webhook/razorpay`
- Active events: check `qr_code.credited`
- Set a webhook secret, and put the same value in `.env` as `RAZORPAY_WEBHOOK_SECRET`

## 4. Deploy it somewhere real

This needs to run on an actual server (not a static host), because it holds your Razorpay secret key and talks to Razorpay's API directly. Easiest options:
- **Render** or **Railway**: connect this folder as a repo, set the env vars in their dashboard, deploy — both give you a free HTTPS URL.
- **A basic VPS** (e.g. DigitalOcean): `git clone`, `npm install`, run with `pm2 start server.js` so it survives reboots, put it behind nginx with HTTPS (Razorpay QR pages and webhooks need HTTPS).

Whichever you use, **use HTTPS** and **never commit your `.env` file**.

## 5. On the day of the event

- Print/write each stall's key on a card, or share it individually so stall owners don't see each other's keys
- Each stall owner opens `stall.html` on their own phone, enters their key once (it's saved in their browser)
- They just type an amount + description each time a customer pays

## 6. Get your data

`/admin.html` → **Download CSV** → gives you every payment across every stall: amount, description, stall name, status (pending/paid), and timestamps.

## Notes on what this does and doesn't cover

- **Security**: stall keys are stored as SHA-256 hashes, not plaintext. Admin routes are protected by a single shared password — fine for a small event, but if you want per-stall-owner accountability beyond the key, you'd want real user accounts.
- **QR expiry**: each QR is set to expire after 15 minutes (`close_by`) — adjust in `server.js` if you want it different.
- **Polling vs webhook**: polling works but adds a few seconds of lag and load; the webhook is instant. Set up both — webhook does the real work, polling is the safety net if the webhook is delayed.
- **No refund flow**: this only creates and tracks payments in. If you need refunds, that's a separate Razorpay API call you'd add to the admin page.
