import os
import requests

def send_telegram_alert(job_title, job_url):
    # Pull credentials securely from GitHub environment variables
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    # Format the message text
    message_text = f"🚨 *New Job Posted!*\n\n*Role:* {job_title}\n*Link:* [Click Here]({job_url})"
    
    # Telegram API Endpoint
    telegram_url = f"https://telegram.org{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "Markdown" # Allows bolding and links
    }
    
    # Send the request
    response = requests.post(telegram_url, json=payload)
    
    if response.status_code == 200:
        print("Telegram alert sent successfully!")
    else:
        print(f"Failed to send Telegram alert: {response.text}")
