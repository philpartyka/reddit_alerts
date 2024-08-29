import praw
import os
import requests
import json
import time
import signal
from prawcore.exceptions import ServerError
from datetime import datetime
from dotenv import load_dotenv
from threading import Thread

# Fetch Telegram Bot settings from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

load_dotenv()
reddit = praw.Reddit(
    client_id=os.getenv('REDDIT_CLIENT_ID'),
    client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
    user_agent="python:com.reddit.reddit-new-post-checker:v2.0.0 (by /u/fatphil)"
)

# Global flag to signal termination
terminate = False

def signal_handler(signum, frame):
    global terminate
    terminate = True
    print("\nTermination signal received. Shutting down...")

signal.signal(signal.SIGINT, signal_handler)

def send_telegram_message(message, parse_mode="MarkdownV2", disable_preview=True, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_preview
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    response = requests.post(url, json=payload)
    return response.json()

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def escape_markdown(text):
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join('\\' + char if char in escape_chars else char for char in text)

def format_timestamp(unix_time):
    return datetime.fromtimestamp(unix_time).strftime("%Y-%m-%d %H:%M:%S")

def get_banned_authors():
    try:
        with open("banned.txt", "r") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []

def get_updates(offset=0):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {
        "offset": offset,
        "timeout": 30
    }
    response = requests.get(url, params=params)
    return response.json()

def add_author_to_banned(submission_id):
    try:
        submission = reddit.submission(id=submission_id)
        author = submission.author.name if submission.author else "[deleted]"
        
        file_path = os.path.join(os.path.dirname(__file__), "banned.txt")
        print(f"Attempting to write to file: {file_path}")
        
        with open(file_path, "a+") as f:
            f.seek(0)
            banned_authors = f.read().splitlines()
            if author not in banned_authors:
                f.write(f"{author}\n")
                f.flush()  # Ensure the data is written to disk
                os.fsync(f.fileno())  # Force write to disk
                print(f"{get_timestamp()} - Added {author} to banned.txt")
            else:
                print(f"{get_timestamp()} - {author} is already in banned.txt")
        
        # Verify the file contents after writing
        with open(file_path, "r") as f:
            content = f.read()
            print(f"Current contents of banned.txt: {content}")
    except Exception as e:
        print(f"Error adding author to banned.txt: {e}")

def handle_updates():
    global terminate
    offset = 0
    while not terminate:
        try:
            #print(f"{get_timestamp()} - Checking for updates...")
            updates = get_updates(offset)
            #print(f"{get_timestamp()} - Received {len(updates.get('result', []))} updates")
            for update in updates.get("result", []):
                if terminate:
                    break
                offset = update["update_id"] + 1
                print(f"{get_timestamp()} - Processing update {update['update_id']}")
                if "callback_query" in update:
                    callback_query = update["callback_query"]
                    data = callback_query["data"]
                    print(f"{get_timestamp()} - Received callback query with data: {data}")
                    if data.startswith("thumbs_down_"):
                        submission_id = data.split("_")[2]
                        print(f"{get_timestamp()} - Thumbs down clicked for submission ID: {submission_id}")
                        add_author_to_banned(submission_id)
                        answer_callback_query(callback_query['id'])
        except Exception as e:
            print(f"Error in handle_updates: {e}")
        time.sleep(1)  # Add a small delay to prevent excessive API calls         

def answer_callback_query(callback_query_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    payload = {
        "callback_query_id": callback_query_id,
        "text": "Thanks for your feedback!"
    }
    requests.post(url, json=payload)

def monitor_reddit():
    global terminate
    load_dotenv()

    max_retries = 5
    retry_delay = 60  # seconds

    while not terminate:
        try:
            reddit = praw.Reddit(
                client_id=os.getenv('REDDIT_CLIENT_ID'),
                client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
                user_agent="python:com.reddit.reddit-new-post-checker:v2.0.0 (by /u/fatphil)"
            )
            
            subreddit_dict = {
                "frugalmalefashion": "FMF",
                "BoardGameExchange": "BGE",
                "buildapcsales": "BAPS"
            }

            subreddit_names = "+".join(subreddit_dict.keys())
            subreddit = reddit.subreddit(subreddit_names)

            print(f"{get_timestamp()} - Monitoring {', '.join(subreddit_dict.keys())} for new submissions...")
            print("-" * 50)  
    
            for submission in subreddit.stream.submissions(skip_existing=True):
                if terminate:
                    break
                print(f"Title: {submission.title}")
                print(f"Subreddit: r/{submission.subreddit}")
                if submission.subreddit == "buildapcsales":
                    print(f"Submission URL: {submission.url}")
                print(f"Submission URL: https://reddit.com{submission.permalink}")
                print(f"submission id:{submission.id}")
                print(f"Created: {format_timestamp(submission.created_utc)}")
                print(f"Score: {submission.score}")
                
                subreddit_shorthand = subreddit_dict.get(str(submission.subreddit), str(submission.subreddit))

                escaped_title = escape_markdown(submission.title)
                escaped_shorthand = escape_markdown(subreddit_shorthand)

                tg_alert = f"[{escaped_shorthand}] \\| [{escaped_title}](https://reddit.com{submission.permalink})"
                banned_authors = get_banned_authors()
                
                if str(submission.subreddit).lower() == "buildapcsales":
                    if "woot.com" in submission.url.lower():
                        response = send_telegram_message(tg_alert)
                        if response.get('ok'):
                            print(f"{get_timestamp()} - Telegram alert sent for r/buildapcsales (woot.com link)")
                        else:
                            print(f"{get_timestamp()} - Failed to send Telegram alert for r/buildapcsales woot.com link: {response.get('description')}")
                    else:
                        print(f"{get_timestamp()} - Skipped r/buildapcsales submission (non-woot.com link)")
                else:
                    reply_markup = None
                    if str(submission.subreddit).lower() == "boardgameexchange":
                        # Check if the author is in the banned list
                        if submission.author and submission.author.name in banned_authors:
                            print(f"{get_timestamp()} - Skipped submission from banned author: {submission.author.name}")
                            continue  # Skip to the next submission
                        reply_markup = {
                            "inline_keyboard": [[
                                {
                                    "text": "👎",
                                    "callback_data": f"thumbs_down_{submission.id}"
                                }
                            ]]
                        }
                    
                    response = send_telegram_message(tg_alert, reply_markup=reply_markup)
                    if response.get('ok'):
                        print(f"{get_timestamp()} - Telegram alert sent for r/{submission.subreddit}")
                    else:
                        print(f"{get_timestamp()} - Failed to send Telegram alert: {response.get('description')}")

                print("-" * 50)
            
        except ServerError as e:
            print(f"Encountered ServerError: {e}")
            for i in range(max_retries):
                print(f"Retrying in {retry_delay} seconds... (Attempt {i+1}/{max_retries})")
                time.sleep(retry_delay)
                try:
                    # Try to reinitialize the Reddit instance
                    reddit = praw.Reddit(
                        client_id=os.getenv('REDDIT_CLIENT_ID'),
                        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
                        user_agent="python:com.reddit.fmf-new-post-checker:v1.1.0 (by /u/fatphil)"
                    )
                    subreddit = reddit.subreddit(subreddit_names)
                    break  # If successful, break out of the retry loop
                except ServerError:
                    continue  # If it fails again, continue to the next retry
            else:
                print("Max retries reached. Exiting.")
                break
        except Exception as e:
            print(f"Encountered unexpected error: {e}")
            if terminate:
                    break
            break         

def main():
    # Start the Reddit monitoring in a separate thread
    reddit_thread = Thread(target=monitor_reddit)
    reddit_thread.start()

    # Start handling Telegram updates in the main thread
    try:
        handle_updates()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Shutting down...")
    finally:
        global terminate
        terminate = True
        reddit_thread.join()
        print("Script terminated.")

if __name__ == "__main__":
    main()