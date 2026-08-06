import os
import sys
import json
import requests
from bs4 import BeautifulSoup

# File name used to remember jobs we have already seen between runs
CACHE_FILE = "seen_jobs.json"

def load_seen_jobs():
    """Loads previously found job IDs from a local JSON file to prevent spam."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen_jobs(seen_ids):
    """Saves updated job IDs back to the local tracking file."""
    with open(CACHE_FILE, "w") as f:
        json.dump(list(seen_ids), f)

def send_telegram_alert(job_title, job_url):
    """Sends an instant push notification alert to your phone via Telegram."""
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("Error: Missing Telegram credentials in environment variables.")
        return

    message_text = f"🚨 *New Job Posted!*\n\n*Role:* {job_title}\n*Link:* [Click Here]({job_url})"
    telegram_url = f"https://telegram.org{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(telegram_url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"Notification successfully pushed for: {job_title}")
        else:
            print(f"Telegram API Error: {response.text}")
    except Exception as e:
        print(f"Network error sending Telegram notification: {e}")

def main():
    # 1. Fetch system credentials safely from your hidden GitHub Secrets
    login_url = os.environ.get('LOGIN_URL')
    jobs_url = os.environ.get('JOBS_URL')
    username = os.environ.get('AUTH_USERNAME')
    password = os.environ.get('AUTH_PASSWORD')

    if not all([login_url, jobs_url, username, password]):
        print("Execution Failed: Missing required site credentials in configuration environments.")
        sys.exit(1)

    # 2. Start a persistent network session to auto-save and reuse authentication cookies
    session = requests.Session()
    
    # Emulate a standard browser profile header to bypass simple firewall blocks
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    # 3. Define the exact form values required by your portal's login screen
    # NOTE: Check your portal's HTML form inputs. Change 'username'/'password' below if the website uses 'email' or 'login_password' fields.
    login_data = {
        "username": username,
        "password": password
    }

    print("Authenticating session access against login gateway...")
    try:
        login_response = session.post(login_url, data=login_data, timeout=15)
        if login_response.status_code != 200:
            print(f"Authentication failed: Server returned HTTP status {login_response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"Critical connection failure during login process: {e}")
        sys.exit(1)

    # 4. Pull the target data page using our freshly authenticated login cookies
    print("Navigating securely to internal job directory dashboard...")
    try:
        jobs_response = session.get(jobs_url, timeout=15)
        if jobs_response.status_code != 200:
            print(f"Failed to access secure dashboard: Received status {jobs_response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"Critical connection failure parsing dashboard view: {e}")
        sys.exit(1)

    # 5. Parse the page's HTML structure
    soup = BeautifulSoup(jobs_response.text, 'html.parser')
    
    # Load previously seen posts from cache to ensure we only send notifications for new postings
    seen_jobs = load_seen_jobs()
    new_jobs_found = False

    # 6. Locate job entries on the page
    # NOTE: You will need to inspect your target website's HTML code and adjust these tags.
    # Below is a standard fallback example looking for links inside common article/job container tags.
    job_elements = soup.find_all(['div', 'li', 'tr'], class_=lambda c: c and 'job' in c.lower())
    
    # If standard keyword search yields nothing, fall back to extracting all text anchors
    if not job_elements:
        job_elements = soup.find_all('a', href=True)

    print(f"Scanning data stream... Found {len(job_elements)} potential items to evaluate.")

    for element in job_elements:
        title = element.get_text(strip=True)
        url = element.get('href', jobs_url)
        
        # Ensure URLs are complete web addresses
        if url.startswith('/'):
            # Reconstruct absolute paths using your base dashboard domain link
            from urllib.parse import urljoin
            url = urljoin(jobs_url, url)

        # Unique identifier to determine if we've seen this item before
        job_id = url if url != jobs_url else title

        # Verify it looks like a valid item and is not already checked off inside our tracking cache
        if title and job_id not in seen_jobs:
            print(f"Identified fresh listing update: {title}")
            
            # Send notification directly to your phone via Telegram bot
            send_telegram_alert(title, url)
            
            # Record tracking ID to prevent duplicate spam notifications
            seen_jobs.add(job_id)
            new_jobs_found = True

    # 7. Persist cached index data back to repository workspace tracking sheets
    if new_jobs_found:
        save_seen_jobs(seen_jobs)
    else:
        print("Scan complete: No new job openings found since the last check.")

if __name__ == "__main__":
    main()
