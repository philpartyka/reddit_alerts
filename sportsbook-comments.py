import praw
import requests
import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from prawcore.exceptions import PrawcoreException, ResponseException, RequestException
import pytz
import schedule

# Load environment variables
load_dotenv()

# Initialize the Reddit API client
def init_reddit():
    return praw.Reddit(
        client_id=os.getenv('REDDIT_CLIENT_ID'),
        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
        user_agent="python:com.reddit.sportsbook-comment-stream:v1.1.0 (by /u/fatphil)"
    )

# Fetch Telegram Bot settings from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error sending Telegram message: {e}")

def find_latest_thread(reddit):
    subreddit = reddit.subreddit("sportsbook")
    latest_submission = None
    latest_timestamp = 0
    
    for submission in subreddit.new(limit=30):
        if "Sportsbook Promos" in submission.title:
            if submission.created_utc > latest_timestamp:
                latest_submission = submission
                latest_timestamp = submission.created_utc
    
    return latest_submission

def process_existing_comments(submission):
    comments = []
    submission.comments.replace_more(limit=None)
    for comment in submission.comments:
        if comment.parent_id.startswith('t3_'):
            author = comment.author.name if comment.author else "[deleted]"
            if author.lower() != "sbpotdbot":
                comments.append(f"u/{author}:\n{comment.body}")
    return comments    

def monitor_comments(reddit, submission, seen_comments):
    try:
        submission.comments.replace_more(limit=None)
        
        for comment in submission.comments:
            if comment.parent_id.startswith('t3_') and comment.id not in seen_comments:
                author = comment.author.name if comment.author else "[deleted]"
                
                if author.lower() != "sbpotdbot":
                    print(f"{get_timestamp()} - New comment from u/{author}: {comment.body}")
                    message = f"u/{author}:\n{comment.body}"
                    send_telegram_message(message)
                seen_comments.add(comment.id)
    
    except (PrawcoreException, ResponseException, RequestException) as e:
        print(f"{get_timestamp()} - Reddit API error: {e}")
    except Exception as e:
        print(f"{get_timestamp()} - Unexpected error: {e}")

def check_for_new_thread(reddit, current_submission):
    new_submission = find_latest_thread(reddit)
    if new_submission and new_submission.id != current_submission.id:
        print(f"{get_timestamp()} - New thread found: {new_submission.title}")
        existing_comments = process_existing_comments(new_submission)
        for comment in existing_comments:
            send_telegram_message(comment)
        return new_submission
    return current_submission

def main():
    reddit = init_reddit()
    current_submission = find_latest_thread(reddit)
    if not current_submission:
        print("No suitable thread found. Exiting.")
        return

    print(f"{get_timestamp()} - Monitoring thread: {current_submission.title}")
    seen_comments = set()
    
    # Initialize seen_comments with existing top-level comments
    for comment in current_submission.comments:
        if comment.parent_id.startswith('t3_'):
            seen_comments.add(comment.id)
    
    # Schedule the check for a new thread
    schedule.every().day.at("20:00").do(lambda: check_for_new_thread(reddit, current_submission))
    
    while True:
        schedule.run_pending()
        
        # Check for a new thread (this will only update if a new thread is found)
        new_submission = check_for_new_thread(reddit, current_submission)
        if new_submission != current_submission:
            current_submission = new_submission
            seen_comments = set()  # Reset seen comments for the new thread
            print(f"{get_timestamp()} - Switched to new thread: {current_submission.title}")
        
        monitor_comments(reddit, current_submission, seen_comments)
        time.sleep(30)  # Wait for 30 seconds before the next iteration

if __name__ == "__main__":
    main()