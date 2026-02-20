# Telegram Notifications Setup Guide

SuperviseMe now supports Telegram notifications to keep users informed about thesis activities in real-time.

## Table of Contents
1. [Admin Setup](#admin-setup)
2. [User Configuration](#user-configuration)
3. [Notification Types](#notification-types)
4. [Troubleshooting](#troubleshooting)
5. [API Reference](#api-reference)

## Admin Setup

### Step 1: Create a Telegram Bot

1. Open Telegram and start a chat with [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow the instructions to choose a name and username for your bot
4. Save the **Bot Token** (format: `123456789:ABCdefGHIjklMNOpqrSTUvwxyz`)
5. Note the **Bot Username** (without @)

### Step 2: Configure Bot in SuperviseMe

1. Log in as an administrator
2. Navigate to **Admin** > **Annotation & Notification Settings**
3. Scroll down to the **Telegram Bot Configuration** section
4. Enter your **Bot Token** and **Bot Username**
5. Select which notification types should be available via Telegram
6. Click **Test Bot Connection** to verify the configuration
7. Click **Save Telegram Configuration**

### Step 3: Environment Configuration (Optional)

Add these variables to your `.env` file:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_BOT_USERNAME=your_bot_username_here
BASE_URL=https://your-superviseme-domain.com
```

## User Configuration

### Step 1: Get Your Telegram User ID

1. Start a chat with your SuperviseMe bot on Telegram
2. Send any message (e.g., "Hello")
3. The bot will reply with your Telegram User ID (a number like `123456789`)

### Step 2: Configure Notifications in Profile

1. Log in to SuperviseMe
2. Go to your **Profile** page
3. Scroll down to the **Telegram Notifications** section
4. Enter your **Telegram User ID** from Step 1
5. Click **Verify** to test the connection
6. Enable **Telegram Notifications**
7. Select which notification types you want to receive
8. Click **Send Test Message** to verify everything works
9. Click **Save Settings**

## Notification Types

| Type | Icon | Description | Available To |
|------|------|-------------|--------------|
| **New Thesis Update** | 📝 | When a student posts a new thesis update | Supervisors |
| **New Supervisor Feedback** | 💬 | When a supervisor provides feedback on your thesis | Students |
| **Task Assignment** | ✅ | When a new task is assigned to you | Students, Supervisors |
| **Task Completion** | 🎯 | When a task assigned by you is completed | Students, Supervisors |
| **Thesis Status Change** | 📊 | When your thesis status is updated | Students |
| **Deadline Reminder** | ⏰ | Reminders for upcoming deadlines | Students, Supervisors |
| **Weekly Summary** | 📈 | Weekly summary of thesis activities | Supervisors |

### Frequency and Granularity

- **Immediate**: Notifications are sent instantly when events occur
- **Batched**: Multiple notifications can be grouped together (future feature)
- **Scheduled**: Weekly summaries are sent at configured times
- **Priority-based**: High-priority notifications (deadlines) bypass user settings

## Troubleshooting

### Common Issues

#### "Bot not configured" error
- **Cause**: Admin hasn't set up the Telegram bot
- **Solution**: Contact your administrator to configure the bot in admin settings

#### "Chat not found" error
- **Cause**: You haven't started a conversation with the bot
- **Solution**: Message the bot on Telegram first, then retry verification

#### "Telegram notifications not enabled for user"
- **Cause**: You haven't enabled notifications in your profile
- **Solution**: Enable Telegram notifications in your profile settings

#### Test message not received
- **Cause**: Various issues (wrong User ID, bot token, network issues)
- **Solutions**:
  1. Verify your Telegram User ID is correct
  2. Ensure you've started a chat with the bot
  3. Check if bot is still active (contact admin)
  4. Try disabling and re-enabling notifications

### Debug Information

Administrators can check:
- Bot connection status in admin settings
- System logs for Telegram API errors
- User configuration in the database

## API Reference

### Admin Endpoints

#### Configure Telegram Bot
```http
POST /admin/telegram/config
Content-Type: application/json

{
  "bot_token": "123456789:ABCdefGHIjklMNOpqrSTUvwxyz",
  "bot_username": "YourBotName",
  "is_active": true,
  "notification_types": ["new_update", "new_feedback", "todo_assigned"],
  "frequency_settings": {}
}
```

#### Test Bot Connection
```http
POST /admin/telegram/test
```

#### Get Notification Types
```http
GET /admin/telegram/notification-types
```

### User Endpoints

#### Configure User Settings
```http
POST /profile/telegram/config
Content-Type: application/json

{
  "telegram_user_id": "123456789",
  "telegram_enabled": true,
  "notification_types": ["new_feedback", "todo_assigned"]
}
```

#### Verify Telegram Connection
```http
POST /profile/telegram/verify
Content-Type: application/json

{
  "telegram_user_id": "123456789"
}
```

#### Send Test Message
```http
POST /profile/telegram/test
```

### Database Schema

#### User_mgmt Table (New Fields)
```sql
ALTER TABLE user_mgmt ADD COLUMN telegram_user_id VARCHAR(50) NULL;
ALTER TABLE user_mgmt ADD COLUMN telegram_enabled BOOLEAN DEFAULT 0 NOT NULL;
ALTER TABLE user_mgmt ADD COLUMN telegram_notification_types TEXT NULL;
```

#### Notification Table (New Fields)
```sql
ALTER TABLE notification ADD COLUMN telegram_sent BOOLEAN DEFAULT 0 NOT NULL;
ALTER TABLE notification ADD COLUMN telegram_sent_at INTEGER NULL;
```

#### New TelegramBotConfig Table
```sql
CREATE TABLE telegram_bot_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_token VARCHAR(200) NOT NULL,
    bot_username VARCHAR(100) NOT NULL,
    webhook_url VARCHAR(500) NULL,
    is_active BOOLEAN DEFAULT 1 NOT NULL,
    notification_types TEXT NOT NULL,
    frequency_settings TEXT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
```

## Security Considerations

1. **Bot Token Security**: Keep your bot token secure and never expose it in client-side code
2. **User ID Verification**: Users must verify their Telegram User ID to prevent impersonation
3. **Rate Limiting**: Telegram API has rate limits; the system respects these automatically
4. **Data Privacy**: Only notification content is sent to Telegram; no sensitive data is exposed

## Migration

Run the migration script to add Telegram functionality to existing installations:

```bash
python migrate_telegram.py
```

This will:
- Add new database columns
- Create the telegram_bot_config table
- Set default notification preferences for existing users
- Preserve existing data integrity