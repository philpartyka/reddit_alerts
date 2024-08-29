# Alerts of New Posts on reddit

I wrote these scripts to monitor new posts when they are submitted to certain subreddits where time sensisitivity is a concern.  I was using an alerts app on my phone to receive these alerts but I found that making my own scripts returned the results faster and offered me more customization. 

## Contents

All relevant messages/posts are sent via Telegram API to a Telegram bot that I can access on my phone.

- r/buildapcsales monitor = Looks for new posts in the buildapcsales subreddit and if its a fast moving post then it messages it.
- r/sportsbook comments monitor = Sends new comments in the daily promo threads on the sportsbook subreddit.  This script also monitors when a new daily post is created so it can start monitoring it. 
- r/frugalmalefashion monitor = Just plainly returns every new post from this subreddit.
- r/BoardGameExchange = Looks for new posts and sends the post with a thumbs down button.  If this button is pressed then the user is blacklisted so I no longer see posts from that user. 
