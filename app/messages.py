"""All user-facing message templates. No hardcoded strings in handlers."""

START_MESSAGE = (
    "👋 Hi there, <b>{first_name}</b>!\n\n"
    "🔰 I am <b>LinkShortify Bot</b> — a powerful link shortener with advanced features.\n\n"
    "➡️ /help — all available commands\n"
    "➡️ /api — link your LinkShortify account\n"
    "➡️ /features — explore what I can do"
)

WELCOME_API_MESSAGE = (
    "✅ <b>Account Connected!</b>\n\n"
    "Your LinkShortify account has been linked successfully.\n"
    "<b>API Key:</b> <code>{api_key}</code>\n\n"
    "Send me any post and I will shorten all links for you. 😇"
)

HELP_MESSAGE = (
    "👋 <b>LinkShortify Bot — Help</b>\n\n"
    "<b>Account</b>\n"
    "/api — link your LinkShortify account\n"
    "/account — view account details\n"
    "/balance — view earnings &amp; balance\n"
    "/logout — unlink your account\n\n"
    "<b>Customization</b>\n"
    "/header &lt;text&gt; — prepend text to every message\n"
    "/footer &lt;text&gt; — append text to every message\n"
    "/username @handle — replace all @mentions\n"
    "/hashtag #tag — replace all #hashtags\n"
    "/channel_link t.me/x — replace all channel links\n"
    "/banner_image &lt;url&gt; — attach a banner to responses\n\n"
    "<b>Settings</b>\n"
    "/settings — toggle all features on/off\n\n"
    "❗ Support: {owner_contact}"
)

FEATURES_MESSAGE = (
    "💠 <b>Features</b>\n\n"
    "➡️ Bulk link shortening in any post\n"
    "➡️ Hidden, hyper, button &amp; spoiler links supported\n"
    "➡️ Custom alias shortening ( url | alias format )\n"
    "➡️ Custom header and footer text\n"
    "➡️ Custom banner image\n"
    "➡️ Username, hashtag &amp; channel link replacement\n"
    "➡️ One-tap settings panel\n"
    "➡️ Full account and balance stats\n\n"
    "❗ Need help? {owner_contact}"
)

ABOUT_MESSAGE = (
    "💠 <b>About LinkShortify Bot</b>\n\n"
    "🔰 <b>Version:</b> {version}\n"
    "🔰 <b>Support:</b> {owner_contact}\n"
    "🔰 <b>Updates:</b> @LinkShortify\n"
    '🔰 <b>CPM Rates:</b> <a href="https://linkshortify.com/pages/payment-system-english">Click Here</a>\n'
    '🔰 <b>Payment Proof:</b> <a href="https://linkshortify.com/pages/payment-proofs">Click Here</a>\n\n'
    "❤️ Made with love by LinkShortify ❤️"
)

API_MESSAGE = (
    "🔗 <b>Connect Your LinkShortify Account</b>\n\n"
    "1. Click the button below to open your dashboard.\n"
    "2. Navigate to <b>Extras → Telegram Bot</b>.\n"
    "3. Click <b>Start Telegram Bot</b>.\n\n"
    "🔴 Remove your API token: /logout\n"
    "⚙️ Manage settings: /settings"
)

API_INVALID_MESSAGE = "❌ Invalid API Key. Please check and try again."

API_ALREADY_LINKED_MESSAGE = (
    "⚠️ This API key is already linked to another Telegram account.\n\n"
    "Each LinkShortify API key can only be used with one account.\n"
    "Contact support: {owner_contact}"
)

LOGOUT_MESSAGE = (
    "✅ <b>Account Unlinked</b>\n\n"
    "Your API key has been removed. Use /api to link a new account."
)

ACCOUNT_MESSAGE = (
    "🔰 <b>Account Details</b>\n\n"
    "👤 <b>Username:</b> <code>{username}</code>\n"
    "📧 <b>Email:</b> <code>{email}</code>\n"
    "💳 <b>Withdrawal:</b> {withdrawal_method}\n"
    "📋 <b>Account:</b> <code>{withdrawal_account}</code>\n"
    "🔗 <b>Referral:</b> <code>https://linkshortify.com/ref/{username}</code>"
)

BALANCE_MESSAGE = (
    "🔰 <b>Balance</b>\n\n"
    "👤 <b>Username:</b> {username}\n\n"
    "💰 <b>Publisher Earnings:</b> ${publisher_earnings:.2f}\n"
    "👥 <b>Referral Earnings:</b> ${referral_earnings:.2f}\n"
    "✅ <b>Available Balance:</b> {available_balance}"
)

SETTINGS_MESSAGE = (
    "⚙️ <b>Settings</b>\n\n"
    "🔑 <b>API Key:</b> <code>{api_key}</code>\n"
    "⬆️ <b>Header:</b> {header_text}\n"
    "⬇️ <b>Footer:</b> {footer_text}\n"
    "🏷 <b>Username Replace:</b> {username_replace}\n"
    "🔖 <b>Hashtag Replace:</b> {hashtag_replace}\n"
    "⛓️ <b>Channel Link:</b> {channel_link}\n"
    "🏞 <b>Banner Image:</b> {banner_image}\n\n"
    "Toggle features using the buttons below:"
)

HEADER_USAGE_MESSAGE = (
    "💠 <b>Custom Header</b>\n\n"
    "Added to the <b>top</b> of every processed message.\n\n"
    "➡️ Set: <code>/header Your text here</code>\n"
    "🔴 Remove: <code>/header remove</code>\n"
    "⚙️ Toggle: /settings"
)

FOOTER_USAGE_MESSAGE = (
    "💠 <b>Custom Footer</b>\n\n"
    "Added to the <b>bottom</b> of every processed message.\n\n"
    "➡️ Set: <code>/footer Your text here</code>\n"
    "🔴 Remove: <code>/footer remove</code>\n"
    "⚙️ Toggle: /settings"
)

USERNAME_USAGE_MESSAGE = (
    "💠 <b>Username Replace</b>\n\n"
    "All @mentions in posts will be replaced with yours.\n\n"
    "➡️ Set: <code>/username @yourhandle</code>\n"
    "🔴 Remove: <code>/username remove</code>"
)

HASHTAG_USAGE_MESSAGE = (
    "💠 <b>Hashtag Replace</b>\n\n"
    "All #hashtags in posts will be replaced with yours.\n\n"
    "➡️ Set: <code>/hashtag #yourtag</code>\n"
    "🔴 Remove: <code>/hashtag remove</code>"
)

CHANNEL_LINK_USAGE_MESSAGE = (
    "💠 <b>Channel Link Replace</b>\n\n"
    "All Telegram channel links will be replaced with yours.\n\n"
    "➡️ Set: <code>/channel_link https://t.me/yourchannel</code>\n"
    "🔴 Remove: <code>/channel_link remove</code>"
)

BANNER_IMAGE_USAGE_MESSAGE = (
    "💠 <b>Banner Image</b>\n\n"
    "A banner image will be attached to every processed message.\n\n"
    "➡️ URL: <code>/banner_image https://example.com/banner.png</code>\n"
    "➡️ Reply to an image with: <code>set_image</code>\n"
    "🔴 Remove: <code>/banner_image remove</code>"
)

SUBSCRIBE_MESSAGE = (
    "⚠️ <b>Channel Membership Required</b>\n\n"
    "You must join our channel to use this bot.\n\n"
    "👇 Click below to join, then try again."
)

NOT_REGISTERED_MESSAGE = (
    "🔐 Please link your LinkShortify account first.\n\n"
    "Type /api for instructions."
)

BAN_MESSAGE = (
    "⚠️ You have been banned from using this bot.\n\n"
    "Contact support: {owner_contact}"
)

BANNED_NOTIFICATION_MESSAGE = (
    "⚠️ You have been <b>banned</b> from LinkShortify Bot.\n\n"
    "<b>Reason:</b> {reason}\n\n"
    "Contact support if you believe this is a mistake: {owner_contact}"
)

UNBANNED_NOTIFICATION_MESSAGE = (
    "✅ Your ban has been lifted.\n\n"
    "You can now use LinkShortify Bot again."
)

PROCESSING_MESSAGE = "⏳ Processing your request..."

ERROR_MESSAGE = (
    "⚠️ <b>Something went wrong.</b>\n\n"
    "Please try again later or contact support: {owner_contact}"
)

ADMIN_BAN_SUCCESS = "✅ User <code>{user_id}</code> banned.\n<b>Reason:</b> {reason}"
ADMIN_BAN_USAGE = "Usage: <code>/ban &lt;user_id&gt; &lt;reason&gt;</code>"
ADMIN_UNBAN_SUCCESS = "✅ User <code>{user_id}</code> unbanned."
ADMIN_UNBAN_USAGE = "Usage: <code>/unban &lt;user_id&gt;</code>"
ADMIN_NOT_AUTHORIZED = "🚫 You are not authorized to use this command."

BROADCAST_USAGE = (
    "Reply to a message and send /broadcast to broadcast it to all users."
)
BROADCAST_STARTED = "📢 <b>Broadcasting to {total} users...</b>"
BROADCAST_REPORT = (
    "📢 <b>Broadcast Complete</b>\n\n"
    "✅ Sent: {success}\n"
    "❌ Failed: {failed}\n"
    "🚫 Blocked: {blocked}\n"
    "👥 Total: {total}\n"
    "⏱️ Duration: {duration}s"
)

STATUS_MESSAGE = (
    "📊 <b>Bot Status</b>\n\n"
    "👥 <b>Total Users:</b> {total_users}\n"
    "🚫 <b>Banned:</b> {total_bans}\n"
    "🔗 <b>Links Shortened:</b> {total_links}\n"
    "📨 <b>Messages Processed:</b> {total_messages}\n"
    "📢 <b>Broadcasts Sent:</b> {total_broadcasts}\n\n"
    "<b>This session</b>\n"
    "⚡ <b>Commands:</b> {commands}\n"
    "🔁 <b>Links:</b> {links_session}\n"
    "❗ <b>Errors/hour:</b> {errors_hour}\n\n"
    "🗄️ <b>MongoDB:</b> {mongo_status}\n"
    "⏱️ <b>Uptime:</b> {uptime}\n"
    "🐍 <b>Python:</b> {python_version}\n"
    "🤖 <b>Bot Version:</b> {bot_version}\n"
    "💾 <b>Memory:</b> {memory_usage}"
)

REMOVED_SUCCESS = "✅ {item} removed successfully."
ADDED_SUCCESS = "✅ {item} set successfully."
MUST_START_WITH = "❌ {item} must start with <code>{prefix}</code>"
BANNER_SET_SUCCESS = "✅ Banner image updated successfully."
BANNER_REPLY_ERROR = "⚠️ Please reply to an image to set it as a banner."
BANNER_LOAD_ERROR = "⚠️ Failed to load banner image. Check the URL and try again."
