"""
Workday Dublin Job Agent
Checks Workday career sites for new Dublin openings and sends alerts.
"""
import json
import os
import re
import smtplib
import sys
import time
from email.mime.text import MIMEText
from pathlib import Path

import requests

ROOT = Path(__file__).parent
CONFIG = json.loads((ROOT / "companies.json").read_text())
SEEN_FILE = ROOT / "seen_jobs.json"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (job-alert-agent)",
}
PAGE_SIZE = 20
MAX_PAGES = 10  # safety cap per company


def parse_workday_url(url: str):
    """https://salesforce.wd12.myworkdayjobs.com/en-US/External_Career_Site
       -> (base, tenant, site)"""
    m = re.match(r"https://([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/?#]+)", url)
    if not m:
        raise ValueError(f"Not a recognised Workday URL: {url}")
    tenant, wd, site = m.groups()
    return f"https://{tenant}.{wd}.myworkdayjobs.com", tenant, site


def fetch_jobs(company: dict):
    base, tenant, site = parse_workday_url(company["url"])
    api = f"{base}/wday/cxs/{tenant}/{site}/jobs"
    jobs, offset = [], 0
    for _ in range(MAX_PAGES):
        body = {"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset,
                "searchText": CONFIG.get("search_text", "Dublin")}
        r = requests.post(api, json=body, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        postings = data.get("jobPostings", [])
        for p in postings:
            jobs.append({
                "id": f"{tenant}:{p.get('externalPath')}",
                "company": company["name"],
                "title": p.get("title", ""),
                "location": p.get("locationsText", ""),
                "posted": p.get("postedOn", ""),
                "link": f"{base}/en-US/{site}{p.get('externalPath', '')}",
            })
        offset += PAGE_SIZE
        if offset >= data.get("total", 0) or not postings:
            break
        time.sleep(1)
    return jobs


def is_match(job: dict) -> bool:
    loc = job["location"].lower()
    # "2 Locations" style entries can hide Dublin, so keep them if searchText matched
    if "dublin" not in loc and "ireland" not in loc and "locations" not in loc:
        return False
    title = job["title"].lower()
    include = [k.lower() for k in CONFIG.get("include_keywords", [])]
    exclude = [k.lower() for k in CONFIG.get("exclude_keywords", [])]
    if include and not any(k in title for k in include):
        return False
    if any(k in title for k in exclude):
        return False
    return True


def notify(new_jobs: list):
    lines = [f"• {j['company']} — {j['title']}\n  {j['location']} | {j['posted']}\n  {j['link']}"
             for j in new_jobs]
    text = f"{len(new_jobs)} new Dublin job(s) on Workday:\n\n" + "\n\n".join(lines)
    print(text)

    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if token and chat:
        for i in range(0, len(text), 3900):  # Telegram message limit
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          data={"chat_id": chat, "text": text[i:i + 3900],
                                "disable_web_page_preview": True}, timeout=30)

    wa_phone, wa_key = os.getenv("WHATSAPP_PHONE"), os.getenv("WHATSAPP_APIKEY")
    if wa_phone and wa_key:
        for i in range(0, len(text), 1500):  # keep messages short for WhatsApp
            try:
                requests.get("https://api.callmebot.com/whatsapp.php",
                             params={"phone": wa_phone, "text": text[i:i + 1500],
                                     "apikey": wa_key}, timeout=30)
                time.sleep(3)  # CallMeBot rate limit
            except Exception as e:
                print(f"[warn] WhatsApp failed: {e}", file=sys.stderr)

    user, pwd, to = os.getenv("EMAIL_USER"), os.getenv("EMAIL_APP_PASSWORD"), os.getenv("EMAIL_TO")
    if user and pwd and to:
        msg = MIMEText(text)
        msg["Subject"] = f"[Job Agent] {len(new_jobs)} new Dublin openings"
        msg["From"], msg["To"] = user, to
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(user, pwd)
            s.send_message(msg)


def main():
    seen = set(json.loads(SEEN_FILE.read_text())) if SEEN_FILE.exists() else set()
    first_run = not seen
    new_jobs, errors = [], []

    for company in CONFIG["companies"]:
        try:
            for job in fetch_jobs(company):
                if is_match(job) and job["id"] not in seen:
                    new_jobs.append(job)
                    seen.add(job["id"])
        except Exception as e:
            errors.append(f"{company['name']}: {e}")
            print(f"[warn] {company['name']} failed: {e}", file=sys.stderr)

    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=0))

    if first_run:
        print(f"First run: recorded {len(new_jobs)} existing jobs as baseline, no alert sent.")
    elif new_jobs:
        notify(new_jobs)
    else:
        print("No new jobs.")
    if errors:
        print("Errors:\n" + "\n".join(errors))


if __name__ == "__main__":
    main()