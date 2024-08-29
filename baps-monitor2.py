import praw
import time
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import telegram
import requests

# Load environment variables
load_dotenv()

# Initialize the Reddit API client
reddit = praw.Reddit(
    client_id=os.getenv('REDDIT_CLIENT_ID'),
    client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
    user_agent="python:com.reddit.buildapcsales-rising-post-checker:v1.1.0 (by /u/fatphil)"
)

# Initialize Telegram bot
bot = telegram.Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
chat_id = os.getenv('TELEGRAM_CHAT_ID')

subreddit = reddit.subreddit("buildapcsales")
posts_to_monitor = {}

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def send_telegram_message(message):
    bot.send_message(chat_id=chat_id, text=message)

def check_post_score(post_id):
    try:
        post = reddit.submission(id=post_id)
        return post.score
    except praw.exceptions.PRAWException as e:
        if "503" in str(e):
            print(f"503 error encountered for post {post_id}. Retrying in 60 seconds...")
            time.sleep(60)
            return check_post_score(post_id)
        else:
            raise

def monitor_post(post_id, title):
    start_time = datetime.now()
    while (datetime.now() - start_time) < timedelta(minutes=20):
        current_time = datetime.now() - start_time
        
        if current_time < timedelta(seconds=30):
            time.sleep(3)
        elif current_time < timedelta(minutes=2):
            time.sleep(15)
        else:
            time.sleep(30)
        
        score = check_post_score(post_id)
        print(f"Post {post_id} current score: {score}")
        
        if score >= 3 and current_time <= timedelta(minutes=5):
            send_telegram_message(f"Post reached 3 upvotes within 5 minutes:\n{title}\nhttps://www.reddit.com/r/buildapcsales/comments/{post_id}")
            return
        elif score >= 6 and current_time <= timedelta(minutes=10):
            send_telegram_message(f"Post reached 6 upvotes within 10 minutes:\n{title}\nhttps://www.reddit.com/r/buildapcsales/comments/{post_id}")
            return
        elif score >= 10:
            send_telegram_message(f"Post reached 10 upvotes within 20 minutes:\n{title}\nhttps://www.reddit.com/r/buildapcsales/comments/{post_id}")
            return
    
    del posts_to_monitor[post_id]
    print(f"Stopped monitoring post {post_id}")

def is_recent_post(submission):
    post_time = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
    current_time = datetime.now(timezone.utc)
    return (current_time - post_time) <= timedelta(minutes=20)

def main():
    print(f"{get_timestamp()} - Monitoring buildapcsales for new submissions...")
    print("-" * 50)  

    while True:
        try:
            for submission in subreddit.stream.submissions(skip_existing=True):
                if is_recent_post(submission):
                    post_id = submission.id
                    posts_to_monitor[post_id] = submission.title
                    print(f"New post added: {submission.title} (ID: {post_id})")
                    
                    # Start monitoring the new post in a separate thread
                    import threading
                    threading.Thread(target=monitor_post, args=(post_id, submission.title)).start()
                else:
                    print(f"Skipping old post: {submission.title}")
                
                # Check scores of existing posts
                for post_id in list(posts_to_monitor.keys()):  # Create a copy of the list to iterate over
                    score = check_post_score(post_id)
                    if score >= 10:
                        del posts_to_monitor[post_id]
                        print(f"Post {post_id} exceeded 10 upvotes. Removed from monitoring list.")
        except requests.exceptions.RequestException as e:
            print(f"Network error: {e}. Retrying in 60 seconds...")
            time.sleep(60)
        except Exception as e:
            print(f"An error occurred: {e}. Retrying in 60 seconds...")
            time.sleep(60)

if __name__ == "__main__":
    main()