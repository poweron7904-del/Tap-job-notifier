import os
import sys
import json
import requests

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

def send_telegram_alert(job_title, job_id, job_url, skills, location, package):
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("Error: Missing Telegram credentials.")
        return

    # Clean formatting using markdown parameters
    message_text = (
        f"🚨 *New Job Drive Posted!*\n\n"
        f"*Job ID:* {job_id}\n"
        f"*Role:* {job_title}\n"
        f"*Package:* {package} LPA\n"
        f"*Location:* {', '.join(location)}\n"
        f"*Skills Required:* {', '.join(skills)}\n\n"
        f"🔗 [Open Dashboard]({job_url})"
    )
    
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
            print(f"Notification pushed for Job ID: {job_id}")
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
        
        if login_response.status_code == 401:
            print("Authentication failed: Invalid login credentials provided.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Critical connection failure during login: {e}")
        sys.exit(1)

    print("Navigating securely to internal job directory dashboard...")
    try:
        jobs_response = session.get(jobs_url, timeout=15)
        print(f"Dashboard data response code: {jobs_response.status_code}")
    except Exception as e:
        print(f"Critical connection failure parsing dashboard: {e}")
        sys.exit(1)

    # NATIVE JSON PARSING: Replaced BeautifulSoup completely
    try:
        response_data = jobs_response.json()
        # Accommodates either a raw dictionary containing a 'data' array or a direct list array response
        job_cards = response_data.get('data', []) if isinstance(response_data, dict) else response_data
    except Exception as e:
        print(f"Critical Error: The response is not structured JSON format. Check URL path target. {e}")
        sys.exit(1)

    seen_jobs = load_seen_jobs()
    new_jobs_found = False

    print(f"Scanning data stream... Found {len(job_cards)} job cards to evaluate.")

    for job in job_cards:
        # Extract individual unique string ID field markers safely 
        job_id = str(job.get('jobId', job.get('_id', '')))
        if not job_id:
            continue

        # FILTER EXPIRED OR INVALID DRIVES: Checks API metadata directly
        is_expired = job.get('expired', False)
        on_hold = job.get('onHold', False)
        
        if is_expired or on_hold:
            continue

        # Target metadata attributes extraction fields
        title = job.get('jobTitle', 'Unknown Role')
        skills = job.get('skills', [])
        location = job.get('jobLocation', ['Not Specified'])
        package = job.get('package', 'N/A')

        # Run conditional cache loop deduplication comparison check
        if job_id not in seen_jobs:
            print(f"Identified fresh listing update: {job_id} - {title}")
            
            # Fire alerting trigger sequence tracking updates
            send_telegram_alert(
                job_title=title, 
                job_id=job_id, 
                job_url=jobs_url, 
                skills=skills, 
                location=location, 
                package=package
            )
            
            seen_jobs.add(job_id)
            new_jobs_found = True

    if new_jobs_found:
        save_seen_jobs(seen_jobs)
    else:
        print("Scan complete: No new open jobs found since last run.")
        
    print("--- WORKFLOW SCRIPT END ---")

if __name__ == "__main__":
    main()
