# LinkShortify Bot v2.0

A production-grade Telegram bot that automatically shortens links through [linkshortify.com](https://linkshortify.com) and applies custom branding to posts. Built for content creators and channel admins who earn money from every link click.

---

## Features

- Bulk link shortening in any text post or photo caption
- Custom alias shortening (`url | alias` format)
- Custom header and footer per user
- Username, hashtag, and channel link replacement
- Custom banner image
- One-tap settings panel with inline toggles
- Full account and balance stats
- Force-subscription gate
- Multi-admin system
- Ban/unban with user notification
- Mass broadcast via reply
- Three Telegram logging channels (users, errors, admin actions)
- Processing message deduplication (no spam on fast sends)
- MongoDB with Motor (fully async)

---

## Architecture

```
run.py                    — Entry point (python run.py)

deploy/                   — Everything needed to ship it
  install.sh              — One-command installer + systemd setup
  Dockerfile             — Container image (MongoDB/Motor)
  linkshortify-bot.service — systemd unit template

app/                      — The application package
  bot.py                 — Application setup, error handler, main()
  config.py              — Centralized env-var configuration
  messages.py            — All user-facing strings

  core/
    middleware.py        — Decorators: subscription (cached), auth, admin
    logging.py           — Terminal + rotating-file logging setup
    metrics.py           — In-memory runtime counters (surfaced in /status)

  handlers/
    __init__.py          — register_handlers(app) + metrics tap (group -1)
    user.py              — User commands and settings toggle
    admin.py             — Admin commands (ban, broadcast, status)
    message.py           — Text and photo message processing

  services/
    api_client.py        — LinkShortify HTTP client (pooled, retried, timeout)
    shortener.py         — Concurrent pipeline → ProcessResult(conversions)

  utils/
    html_parser.py       — Link extraction from Telegram HTML
    text_filters.py      — Regex replacements (username, hashtag, channel)
    logger.py            — Centralized escaped+retried Telegram logging
    processing.py        — One-active-processing-message manager

  db/
    __init__.py          — Motor client factory
    database.py          — Full database abstraction layer
```

---

## MongoDB Collections

### `users`
| Field | Type | Description |
|---|---|---|
| `telegram_id` | int (unique index) | Telegram user ID |
| `api_key` | string (unique index) | LinkShortify API key |
| `email` | string | Account email |
| `site_username` | string | LinkShortify username |
| `first_name` | string | Telegram first name |
| `username` | string | Telegram username |
| `settings` | object | All per-user feature settings (see below) |
| `created_at` | datetime | Registration timestamp |
| `updated_at` | datetime | Last modification timestamp |

**settings sub-document:**
```
header_text, footer_text, username_replace, hashtag_replace,
channel_link, banner_image               — stored values
header_enabled, footer_enabled, username_enabled,
hashtag_enabled, channel_enabled, banner_enabled  — bool toggles
```

### `bans`
| Field | Description |
|---|---|
| `telegram_id` | Banned user ID (unique index) |
| `reason` | Ban reason text |
| `banned_by` | Admin Telegram ID |
| `created_at` | Timestamp |

### `broadcasts`
| Field | Description |
|---|---|
| `initiated_by` | Admin Telegram ID |
| `success_count` | Users reached |
| `failed_count` | Failed deliveries |
| `timestamp` | Broadcast time (indexed) |

### `stats`
Single document (`_id: "global"`) tracking:
- `total_links_shortened`
- `total_messages_processed`

---

## Environment Variables

Copy `.env.example` to `.env` and fill in all values.

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | Yes | Telegram bot token from @BotFather |
| `MONGODB_URI` | Yes | MongoDB connection URI |
| `MONGODB_DB_NAME` | | Database name (default: `linkshortify`) |
| `LINKSHORTIFY_API_URL` | | Shortening endpoint |
| `LINKSHORTIFY_STATS_URL` | | User stats endpoint |
| `CHANNEL_USERNAME` | | Required join channel (e.g. `@mychannel`) |
| `ADMINS` | Yes | Comma-separated admin Telegram IDs |
| `OWNER_CONTACT` | | Support handle shown in messages |
| `USER_LOG_GROUP` | | Channel for user activity logs |
| `ERROR_LOG_GROUP` | | Channel for exception logs |
| `ADMIN_LOG_GROUP` | | Channel for admin action logs |
| `PROCESSING_MESSAGE_ENABLED` | | Show processing message (default: `true`) |
| `BROADCAST_BATCH_SIZE` | | Users per broadcast batch (default: `25`) |
| `ENVIRONMENT` | | Label shown in error logs (default: `production`) |
| `API_TIMEOUT` | | External API timeout in seconds (default: `15`) |
| `API_RETRIES` | | Transient-failure retries for API calls (default: `2`) |
| `SUB_CACHE_TTL` | | Subscription-check cache TTL in seconds (default: `300`) |
| `LOG_DIR` | | Directory for the rotating log file (default: `logs`) |
| `LOG_FILE` | | Log file name (default: `bot.log`) |
| `LOG_LEVEL` | | Root log level (default: `INFO`) |

---

## Logging

The bot logs through one centralized funnel. Every message is HTML-escaped
before being sent with `parse_mode=HTML` (unescaped tracebacks contain
`<module>`, `<`, `>`, `&` and make Telegram reject the message — the historic
cause of "missing" error logs). Telegram sends are retried and never block a
handler.

**Three destinations for every error:** terminal → rotating file (`logs/bot.log`)
→ Error Logs group. A Telegram outage can never make an error disappear.

| Group | Events logged |
|---|---|
| **User Logs** (`USER_LOG_GROUP`) | New user (first `/start` only, deduplicated) · API linked (masked key) · Link conversion (type, count, original→short) |
| **Error Logs** (`ERROR_LOG_GROUP`) | Every handler exception, background-task exception, API/DB error — with stack trace, source `file:line`, user, action, and environment |
| **Admin Logs** (`ADMIN_LOG_GROUP`) | Ban · Unban · Broadcast started (content summary) · Broadcast completed (success/failed/blocked/duration) · Status |

New-user events are deduplicated at the database level — a user document is
created on first contact, so the "New User" message fires exactly once, ever.

---

## Installation

### Requirements
- Python 3.13+
- MongoDB 6+

### Quick Install (Linux with systemd)

```bash
git clone <repo>
cd linkshortify-master
cp .env.example .env
# Edit .env with your credentials
sudo bash deploy/install.sh
```

This will create a virtual environment, install dependencies, and install + start a systemd service.

### Manual Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env
python run.py
```

### Docker

```bash
docker build -f deploy/Dockerfile -t linkshortify-bot .
docker run --env-file .env linkshortify-bot
```

---

## Deployment (systemd)

After `sudo bash deploy/install.sh`:

```bash
# Check status
sudo systemctl status linkshortify-bot

# View live logs
sudo journalctl -u linkshortify-bot -f

# Restart
sudo systemctl restart linkshortify-bot

# Stop
sudo systemctl stop linkshortify-bot
```

### Manual systemd setup

Edit `deploy/linkshortify-bot.service`, replace `YOUR_USER` and the paths, then:

```bash
sudo cp deploy/linkshortify-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable linkshortify-bot
sudo systemctl start linkshortify-bot
```

---

## Commands

### User Commands

| Command | Description |
|---|---|
| `/start` | Welcome; `?start=<api_key>` links an account |
| `/help` | All available commands |
| `/about` | Bot info and links |
| `/features` | Full feature list |
| `/api` | Instructions to connect your LinkShortify account |
| `/logout` | Unlink your account |
| `/account` | Account details and referral link |
| `/balance` | Earnings and available balance |
| `/settings` | Toggle all features on/off |
| `/header <text>` | Set header; `/header remove` clears it |
| `/footer <text>` | Set footer; `/footer remove` clears it |
| `/username @handle` | Set username replacement |
| `/hashtag #tag` | Set hashtag replacement |
| `/channel_link t.me/x` | Set channel link replacement |
| `/banner_image <url>` | Set banner image URL |

### Admin Commands (ADMINS list only)

| Command | Description |
|---|---|
| `/ban <id> <reason>` | Ban a user (notifies them) |
| `/unban <id>` | Unban a user (notifies them) |
| `/broadcast` | Reply to any message, then send this to broadcast |
| `/status` | Bot stats, uptime, memory, MongoDB health |

---

## MySQL to MongoDB Migration

The v2 rewrite replaces MySQL/SQLAlchemy with MongoDB/Motor. User data must be migrated manually.

Column mapping:

| MySQL (users table) | MongoDB (users.settings) |
|---|---|
| `telegram_id` | `telegram_id` |
| `user_api` | `api_key` |
| `email` | `email` |
| `site_username` | `site_username` |
| `header` | `settings.header_text` |
| `footer` | `settings.footer_text` |
| `username` | `settings.username_replace` |
| `hashtag` | `settings.hashtag_replace` |
| `channel_link` | `settings.channel_link` |
| `banner_path` | `settings.banner_image` |

| MySQL (usermeta table) | MongoDB |
|---|---|
| `is_header` | `settings.header_enabled` |
| `is_footer` | `settings.footer_enabled` |
| `is_username` | `settings.username_enabled` |
| `is_hashtag` | `settings.hashtag_enabled` |
| `is_channel_link` | `settings.channel_enabled` |
| `is_banner` | `settings.banner_enabled` |

Import with: `mongoimport --db linkshortify --collection users --file users.json --jsonArray`

---

## Troubleshooting

**Bot won't start:** Verify `BOT_TOKEN` in `.env` is correct.

**MongoDB error:** Check `MONGODB_URI` and that `mongod` is running (`sudo systemctl status mongod`).

**Force-sub not working:** Make the bot an admin of `CHANNEL_USERNAME`.

**Broadcasts failing:** Normal for users who have blocked the bot — `failed_count` increases as expected.

**No logs in channels:** Bot must be admin of all three log channels.
