"""
Hyundai Santa Fe Hybrid Calligraphy Price Alert
------------------------------------------------
Monitors Cars.com, Autotrader, CarGurus, CarMax, and Carvana for
Hyundai Santa Fe Hybrid Calligraphy listings under a price threshold,
within a radius of a ZIP code, and texts you when a new one shows up.

See README.md for setup instructions.
"""

import json
import os
import re
import smtplib
import sys
import time
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from playwright.sync_api import sync_playwright

# ---------------- CONFIG ----------------
ZIP_CODE = os.getenv("SEARCH_ZIP", "21211")
RADIUS_MILES = int(os.getenv("SEARCH_RADIUS", "100"))
MAX_PRICE = int(os.getenv("MAX_PRICE", "34000"))
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "900"))  # 15 min

TRIM_KEYWORDS = ["calligraphy"]
MODEL_KEYWORDS = ["santa fe hybrid", "santa fe hev"]

SEEN_FILE = Path(__file__).parent / "seen_listings.json"

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USERNAME)
EMAIL_TO = os.getenv("EMAIL_TO")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


# ---------------- PERSISTENCE ----------------
def load_seen():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(sorted(seen)))


# ---------------- HELPERS ----------------
def matches_target_car(title: str) -> bool:
    t = (title or "").lower()
    has_model = any(k in t for k in MODEL_KEYWORDS)
    has_trim = any(k in t for k in TRIM_KEYWORDS)
    return has_model and has_trim


def parse_price(text: str):
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def send_email(subject: str, body: str):
    if not all([SMTP_USERNAME, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO]):
        print("[WARN] Email not configured — printing alert instead:\n", body)
        return
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)


# ---------------- SITE SCRAPERS ----------------
# These sites are JS-heavy single-page apps that change markup periodically
# and may occasionally show a CAPTCHA to automated browsers. The selectors
# below are a best-effort starting point. If a scraper stops finding
# results: open the page in a normal browser, right-click a listing card ->
# Inspect, and update the CSS selector strings below to match.

def scrape_cars_com(page):
    url = (
        "https://www.cars.com/shopping/results/"
        f"?stock_type=used&makes[]=hyundai&models[]=hyundai-santa_fe_hybrid"
        f"&zip={ZIP_CODE}&maximum_distance={RADIUS_MILES}&list_price_max={MAX_PRICE}"
    )
    page.goto(url, timeout=30000)
    page.wait_for_selector("div.vehicle-card", timeout=15000)
    results = []
    for c in page.query_selector_all("div.vehicle-card"):
        title_el = c.query_selector("h2.title")
        price_el = c.query_selector("span.primary-price")
        link_el = c.query_selector("a.vehicle-card-link")
        if not (title_el and price_el and link_el):
            continue
        href = link_el.get_attribute("href")
        results.append({
            "site": "Cars.com",
            "title": title_el.inner_text(),
            "price": parse_price(price_el.inner_text()),
            "url": href if href.startswith("http") else f"https://www.cars.com{href}",
        })
    return results


def scrape_autotrader(page):
    url = (
        f"https://www.autotrader.com/cars-for-sale/hyundai/santa-fe-hybrid"
        f"/zip-{ZIP_CODE}?searchRadius={RADIUS_MILES}&maxPrice={MAX_PRICE}"
    )
    page.goto(url, timeout=30000)
    page.wait_for_selector("div[data-cmp='inventoryListing']", timeout=15000)
    results = []
    for c in page.query_selector_all("div[data-cmp='inventoryListing']"):
        title_el = c.query_selector("h2")
        price_el = c.query_selector("[data-cmp='firstPrice']")
        link_el = c.query_selector("a")
        if not (title_el and price_el and link_el):
            continue
        href = link_el.get_attribute("href")
        results.append({
            "site": "Autotrader",
            "title": title_el.inner_text(),
            "price": parse_price(price_el.inner_text()),
            "url": href if href.startswith("http") else f"https://www.autotrader.com{href}",
        })
    return results


def scrape_cargurus(page):
    # CarGurus keys listings to internal entity IDs rather than plain
    # make/model URL slugs, so we drive the on-page search box instead of
    # guessing a query string.
    page.goto(
        f"https://www.cargurus.com/Cars/inventorylisting/viewDetailsFilterViewInventoryListing.action?zip={ZIP_CODE}",
        timeout=30000,
    )
    search_box = page.query_selector("input[type='search']")
    if search_box:
        search_box.fill("Hyundai Santa Fe Hybrid Calligraphy")
        search_box.press("Enter")
        page.wait_for_timeout(3000)
    page.wait_for_selector("div[data-cg-ft='car-blade']", timeout=15000)
    results = []
    for c in page.query_selector_all("div[data-cg-ft='car-blade']"):
        title_el = c.query_selector("h4")
        price_el = c.query_selector("[data-cg-ft='srp-tile-price']")
        link_el = c.query_selector("a")
        if not (title_el and price_el and link_el):
            continue
        href = link_el.get_attribute("href")
        results.append({
            "site": "CarGurus",
            "title": title_el.inner_text(),
            "price": parse_price(price_el.inner_text()),
            "url": href if href.startswith("http") else f"https://www.cargurus.com{href}",
        })
    return results


def scrape_carmax(page):
    url = (
        f"https://www.carmax.com/cars/hyundai/santa-fe-hybrid"
        f"?search={ZIP_CODE}&radius={RADIUS_MILES}&priceRange=0-{MAX_PRICE}"
    )
    page.goto(url, timeout=30000)
    page.wait_for_selector("div.car-tile", timeout=15000)
    results = []
    for c in page.query_selector_all("div.car-tile"):
        title_el = c.query_selector("div.year-make-model")
        price_el = c.query_selector("div.price")
        link_el = c.query_selector("a")
        if not (title_el and price_el and link_el):
            continue
        href = link_el.get_attribute("href")
        results.append({
            "site": "CarMax",
            "title": title_el.inner_text(),
            "price": parse_price(price_el.inner_text()),
            "url": href if href.startswith("http") else f"https://www.carmax.com{href}",
        })
    return results


def scrape_carvana(page):
    url = (
        f"https://www.carvana.com/cars/hyundai-santa-fe-hybrid"
        f"?zip={ZIP_CODE}&distance={RADIUS_MILES}&price-max={MAX_PRICE}"
    )
    page.goto(url, timeout=30000)
    page.wait_for_selector("div[data-qa='result-tile']", timeout=15000)
    results = []
    for c in page.query_selector_all("div[data-qa='result-tile']"):
        title_el = c.query_selector("div[data-qa='vehicle-name']")
        price_el = c.query_selector("div[data-qa='price']")
        link_el = c.query_selector("a")
        if not (title_el and price_el and link_el):
            continue
        href = link_el.get_attribute("href")
        results.append({
            "site": "Carvana",
            "title": title_el.inner_text(),
            "price": parse_price(price_el.inner_text()),
            "url": href if href.startswith("http") else f"https://www.carvana.com{href}",
        })
    return results


SCRAPERS = [scrape_cars_com, scrape_autotrader, scrape_cargurus, scrape_carmax, scrape_carvana]


# ---------------- MAIN ----------------
def run_once():
    seen = load_seen()
    new_hits = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        for scraper in SCRAPERS:
            try:
                listings = scraper(page)
            except Exception as e:
                print(f"[WARN] {scraper.__name__} failed: {e}")
                continue
            for listing in listings:
                if listing["price"] is None or listing["price"] >= MAX_PRICE:
                    continue
                if not matches_target_car(listing["title"]):
                    continue
                if listing["url"] in seen:
                    continue
                new_hits.append(listing)
                seen.add(listing["url"])
        browser.close()

    for hit in new_hits:
        body = f"{hit['site']}: {hit['title']} — ${hit['price']:,}\n{hit['url']}"
        print(f"[{datetime.now().isoformat(timespec='seconds')}] ALERT: {body}")
        send_email(f"Santa Fe Hybrid Calligraphy match on {hit['site']}", body)

    save_seen(seen)
    return new_hits


if __name__ == "__main__":
    if "--loop" in sys.argv:
        print(f"Checking every {CHECK_INTERVAL_SECONDS} seconds. Ctrl+C to stop.")
        while True:
            run_once()
            time.sleep(CHECK_INTERVAL_SECONDS)
    else:
        run_once()
