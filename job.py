import os
import sys
import json
import requests

# Persistent state file stored in the repository
SEEN_JOBS_FILE = "seen_jobs.json"


def load_seen_jobs():
    """Load previously notified job IDs from seen_jobs.json."""
    if not os.path.exists(SEEN_JOBS_FILE):
        print(f"{SEEN_JOBS_FILE} not found. Starting with an empty job history.")
        return set()

    try:
        with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            print(f"Warning: {SEEN_JOBS_FILE} does not contain a JSON list.")
            return set()

        print(f"Loaded {len(data)} previously seen job IDs.")
        return set(str(job_id) for job_id in data)

    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Could not read {SEEN_JOBS_FILE}: {e}")
        return set()


def save_seen_jobs(seen_ids):
    """Save notified job IDs to seen_jobs.json."""
    try:
        with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(seen_ids), f, indent=2)

        print(f"Saved {len(seen_ids)} job IDs to {SEEN_JOBS_FILE}.")

    except OSError as e:
        print(f"Error: Could not save {SEEN_JOBS_FILE}: {e}")
        sys.exit(1)


def send_telegram_alert(
    job_title,
    job_id,
    job_url,
    skills,
    location,
    package
):
    """Send a new-job notification to Telegram."""

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("Error: Missing Telegram credentials.")
        return False

    # Make sure these fields are safe to join even if the API returns
    # unexpected/missing values.
    if not isinstance(skills, list):
        skills = [str(skills)]

    if not isinstance(location, list):
        location = [str(location)]

    message_text = (
        f"🚨 *New Job Drive Posted!*\n\n"
        f"*Job ID:* {job_id}\n"
        f"*Role:* {job_title}\n"
        f"*Package:* {package} LPA\n"
        f"*Location:* {', '.join(map(str, location))}\n"
        f"*Skills Required:* {', '.join(map(str, skills))}\n\n"
        f"🔗 [Open Dashboard]({job_url})"
    )

    telegram_url = (
        f"https://api.telegram.org/bot{bot_token}/sendMessage"
    )

    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "Markdown",
    }

    try:
        response = requests.post(
            telegram_url,
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            print(f"Notification pushed for Job ID: {job_id}")
            return True

        print(f"Telegram API Error: {response.text}")
        return False

    except requests.RequestException as e:
        print(f"Network error sending Telegram: {e}")
        return False


def main():
    print("--- STARTING JOB MONITOR RUN ---")

    jobs_url = os.environ.get("JOBS_URL")

    if not jobs_url:
        print("Execution Failed: JOBS_URL secret came through empty.")
        sys.exit(1)

    # Create HTTP session
    session = requests.Session()

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
    })

    print(
        "Navigating directly to internal job directory "
        "dashboard (no login step)..."
    )

    # Fetch jobs
    try:
        jobs_response = session.get(
            jobs_url,
            timeout=15
        )

        print(
            f"Dashboard data response code: "
            f"{jobs_response.status_code}"
        )

        jobs_response.raise_for_status()

    except requests.RequestException as e:
        print(
            f"Critical connection failure fetching dashboard: {e}"
        )
        sys.exit(1)

    # Parse JSON response
    try:
        response_data = jobs_response.json()

        if isinstance(response_data, dict):
            job_cards = response_data.get("data", [])
        elif isinstance(response_data, list):
            job_cards = response_data
        else:
            print(
                "Critical Error: Unexpected JSON structure "
                "received from dashboard."
            )
            sys.exit(1)

    except (ValueError, json.JSONDecodeError) as e:
        print(
            "Critical Error: The response is not structured "
            f"JSON format. Check URL path target. {e}"
        )
        sys.exit(1)

    # Load persistent job history from repository
    seen_jobs = load_seen_jobs()

    new_jobs_found = False

    print(
        f"Scanning data stream... "
        f"Found {len(job_cards)} job cards to evaluate."
    )

    for job in job_cards:

        if not isinstance(job, dict):
            continue

        # Get job ID
        job_id = str(
            job.get(
                "jobId",
                job.get("_id", "")
            )
        )

        if not job_id:
            continue

        # Ignore expired/on-hold jobs
        is_expired = job.get("expired", False)
        on_hold = job.get("onHold", False)

        if is_expired or on_hold:
            continue

        # Job information
        title = job.get(
            "jobTitle",
            "Unknown Role"
        )

        skills = job.get(
            "skills",
            []
        )

        location = job.get(
            "jobLocation",
            ["Not Specified"]
        )

        package = job.get(
            "package",
            "N/A"
        )

        # Check whether we already notified this job
        if job_id in seen_jobs:
            continue

        print(
            f"Identified fresh listing update: "
            f"{job_id} - {title}"
        )

        # Send Telegram notification
        notification_sent = send_telegram_alert(
            job_title=title,
            job_id=job_id,
            job_url=jobs_url,
            skills=skills,
            location=location,
            package=package
        )

        # Only mark the job as seen if Telegram succeeded
        if notification_sent:
            seen_jobs.add(job_id)
            new_jobs_found = True
        else:
            print(
                f"Job {job_id} was NOT marked as seen "
                "because Telegram notification failed."
            )

    # Save updated state
    if new_jobs_found:
        save_seen_jobs(seen_jobs)
    else:
        print(
            "Scan complete: No new open jobs successfully "
            "notified."
        )

    print("--- WORKFLOW SCRIPT END ---")


if __name__ == "__main__":
    main()
