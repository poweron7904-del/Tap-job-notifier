import os
import sys
import json
import re
import requests
from bs4 import BeautifulSoup

CACHE_FILE = "seen_jobs.json"

def load_seen_jobs():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen_jobs(seen_ids):
    with open(CACHE_FILE, "w") as f:
        json.dump(list(seen_ids), f)

def send_telegram_alert(job_title, job_url):
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("Error: Missing Telegram credentials.")
        return

    message_text = f"🚨 *New Job Posted!*\n\n*Role:* {job_title}\n*Link:* [Click Here]({job_url})"
    
    # FIXED: Replaced standard domain with correct API endpoint prefix and path
    telegram_url = f"https://telegram.org{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(telegram_url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"Notification pushed for: {job_title}")
        else:
            print(f"Telegram API Error: {response.text}")
    except Exception as e:
        print(f"Network error sending Telegram: {e}")

def main():
    print("--- STARTING JOB MONITOR RUN ---")
    
    login_url = os.environ.get('LOGIN_URL')
    jobs_url = os.environ.get('JOBS_URL')
    username = os.environ.get('AUTH_USERNAME')
    password = os.environ.get('AUTH_PASSWORD')

    if not all([login_url, jobs_url, username, password]):
        print("Execution Failed: Secret variables came through empty.")
        sys.exit(1)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json"
    })

    login_data = {
        "email": username,
        "password": password
    }

    print("Authenticating session access against login gateway...")
    try:
        login_response = session.post(login_url, json=login_data, timeout=15)
        print(f"Login landing page response code: {login_response.status_code}")
        
        # DEBUG ADDITION: Print and save login payload response stream
        print("\n--- DEBUG: RAW LOGIN RESPONSE ---")
        print(login_response.text[:1000])  # Prints first 1000 characters
        print("---------------------------------\n")
        with open("login_debug.html", "w", encoding="utf-8") as f:
            f.write(login_response.text)
        
        if login_response.status_code == 401:
            print("Authentication failed: Invalid login credentials provided.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Critical connection failure during login: {e}")
        sys.exit(1)

    print("Navigating securely to internal job directory dashboard...")
    try:
        jobs_response = session.get(jobs_url, timeout=15)
        print(f"Dashboard page response code: {jobs_response.status_code}")
        
        # DEBUG ADDITION: Print and save dashboard payload response stream
        print("\n--- DEBUG: RAW DASHBOARD RESPONSE ---")
        print(jobs_response.text[:2000])  # Prints first 2000 characters
        print("--------------------------------------\n")
        with open("dashboard_debug.html", "w", encoding="utf-8") as f:
            f.write(jobs_response.text)
            
    except Exception as e:
        print(f"Critical connection failure parsing dashboard: {e}")
        sys.exit(1)

    soup = BeautifulSoup(jobs_response.text, 'html.parser')
    seen_jobs = load_seen_jobs()
    new_jobs_found = False

    job_cards = soup.find_all('div', class_=re.compile(r'placement-card_container'))
    print(f"Scanning data stream... Found {len(job_cards)} job cards to evaluate.")

    for card in job_cards:
        id_element = card.find('h3')
        if not id_element:
            continue
        job_id = id_element.get_text(strip=True)

        status_element = card.find('span', class_=re.compile(r'drive-status-chip_chip_container'))
        
        is_closed = False
        if status_element and status_element.get('class'):
            for cls in status_element.get('class'):
                if "closed" in cls.lower():
                    is_closed = True
                    break
                    
        if is_closed or "Expired" in card.get_text():
            continue

        title = "Unknown Role"
        for item in card.find_all('div', class_=re.compile(r'placement-card_item-container')):
            label = item.find('span')
            if label and "Looking for" in label.get_text():
                role_p = item.find('p')
                if role_p:
                    title = role_p.get_text(strip=True)
                break

        if job_id not in seen_jobs:
            print(f"Identified fresh listing update: {job_id} - {title}")
            display_title = f"{job_id}: {title}"
            send_telegram_alert(display_title, jobs_url)
            seen_jobs.add(job_id)
            new_jobs_found = True

    if new_jobs_found:
        save_seen_jobs(seen_jobs)
    else:
        print("Scan complete: No new open jobs found since last run.")
        
    print("--- WORKFLOW SCRIPT END ---")

if __name__ == "__main__":
    main()
