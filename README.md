# Workday Dublin Job Agent

Checks Workday career sites every 2 hours and alerts you to new Dublin openings.

## Setup
1. Create a **private** GitHub repo and upload these files (keep the `.github` folder).
2. Edit `companies.json`: paste any company's Workday careers URL (the part ending
   in the site name, e.g. `https://xyz.wd3.myworkdayjobs.com/Careers`).
   Optional: add `include_keywords` like `["graduate", "software", "data"]`.
3. Add alerts under **Settings > Secrets and variables > Actions**:
   - Telegram: message @BotFather -> /newbot -> copy token into `TELEGRAM_BOT_TOKEN`.
     Message your bot once, open `https://api.telegram.org/bot<TOKEN>/getUpdates`,
     copy `chat.id` into `TELEGRAM_CHAT_ID`.
   - Email (Gmail): `EMAIL_USER`, `EMAIL_TO`, and an App Password as `EMAIL_APP_PASSWORD`.
4. Go to **Actions > Workday Dublin Job Check > Run workflow** once. The first run
   records current jobs silently; after that you only get alerts for new ones.

## Test locally
pip install requests && python agent.py
