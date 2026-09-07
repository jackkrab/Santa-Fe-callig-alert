# Santa Fe Hybrid Calligraphy Price Alert

Checks Cars.com, Autotrader, CarGurus, CarMax, and Carvana for a Hyundai
Santa Fe Hybrid Calligraphy under $34,000 within 100 miles of 21211, and
texts you when a new match shows up.

## 1. Install

```bash
pip install -r requirements.txt
playwright install chromium
```

## 2. Set up email alerts

The default settings work with Gmail's SMTP server; other providers work
too, just swap `SMTP_HOST`/`SMTP_PORT` for theirs.

1. If sending from a Gmail account, create an "app password" (Google
   Account → Security → 2-Step Verification → App passwords) — Gmail
   blocks plain password logins from scripts like this one.
2. Copy `.env.example` to `.env` and fill in `SMTP_USERNAME` (your email),
   `SMTP_PASSWORD` (the app password), `EMAIL_FROM`, and `EMAIL_TO` (where
   you want alerts sent — can be the same address, or your phone's
   email-to-text gateway, e.g. `4105551234@vtext.com` for Verizon, if you'd
   rather it land as a text).
3. Load the env vars before running, e.g.:
   ```bash
   export $(cat .env | xargs)
   ```

If you skip this setup, the script still runs and just prints alerts to
the console instead of emailing — useful for testing.

## 3. Run it

One-time check:
```bash
python santa_fe_alert.py
```

Keep running and re-check every 15 minutes (default; change via
`CHECK_INTERVAL_SECONDS`):
```bash
python santa_fe_alert.py --loop
```

Or run it as a cron job every 15 minutes instead of `--loop` (better if
you don't want to keep a terminal open):
```
*/15 * * * * cd /path/to/this/folder && /usr/bin/python3 santa_fe_alert.py >> log.txt 2>&1
```

It keeps a `seen_listings.json` file next to the script so you only get
texted once per listing, not every single check.

## Things to know

- **Selectors will drift.** These sites redesign their pages periodically,
  and the CSS selectors this script uses to find title/price/link on each
  page will eventually break on one site or another. If a site stops
  producing results, open that site in a normal browser, right-click a
  listing card → Inspect, and update the matching selector in
  `santa_fe_alert.py`.
- **Anti-bot measures.** Some of these sites may occasionally serve a
  CAPTCHA or block to automated browsers, especially if checked very
  frequently. Keep the check interval reasonable (15+ minutes) and don't
  run multiple instances in parallel against the same site.
- **Terms of service.** Automated scraping isn't explicitly authorized by
  these sites' terms. This script is intended for light personal use
  (checking a few times an hour), not high-frequency or commercial
  scraping.
- **Matching logic.** A listing counts as a match if its title contains
  both "Santa Fe Hybrid" (or "Santa Fe HEV") and "Calligraphy" — you can
  loosen or tighten this in `MODEL_KEYWORDS`/`TRIM_KEYWORDS` at the top of
  the script.
