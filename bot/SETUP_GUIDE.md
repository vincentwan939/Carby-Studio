# Carby Studio Telegram Bot - Setup Guide

## Quick Start (5 minutes)

### Step 1: Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Start a chat and send: `/newbot`
3. Follow prompts:
   - Name your bot (e.g., "Carby Studio")
   - Choose username (e.g., "carby_studio_bot") - must end in "bot"
4. **Save the token** BotFather gives you (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Set Environment Variable

```bash
# Add to your ~/.zshrc or ~/.bash_profile
export CARBY_BOT_TOKEN="your_token_here"

# Reload shell
source ~/.zshrc
```

### Step 3: Install Dependencies

```bash
cd /Users/wants01/.openclaw/workspace/carby-studio/bot
pip3 install -r requirements.txt
```

### Step 4: Run the Bot

```bash
cd /Users/wants01/.openclaw/workspace/carby-studio/bot
python3 telegram_interface.py
```

You should see:
```
Starting Carby Bot with Phase 2 components...
```

### Step 5: Test in Telegram

1. Find your bot in Telegram (search for the username you created)
2. Send `/start`
3. You should see the welcome message with buttons:
   - 📋 Projects
   - ➕ New Project
   - ⚙️ More

---

## Making It Permanent (Auto-start)

### Option A: Run in Background with nohup

```bash
cd /Users/wants01/.openclaw/workspace/carby-studio/bot
nohup python3 telegram_interface.py > bot.log 2>&1 &
echo $! > bot.pid
```

To stop:
```bash
kill $(cat bot.pid)
```

### Option B: Create a LaunchAgent (macOS)

Create `~/Library/LaunchAgents/com.carby.bot.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.carby.bot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/wants01/.openclaw/workspace/carby-studio/bot/telegram_interface.py</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>CARBY_BOT_TOKEN</key>
        <string>YOUR_TOKEN_HERE</string>
        <key>CARBY_WORKSPACE</key>
        <string>/Users/wants01/.openclaw/workspace/projects</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/wants01/.openclaw/workspace/carby-studio/bot/bot.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/wants01/.openclaw/workspace/carby-studio/bot/bot.error.log</string>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.carby.bot.plist
```

---

## Troubleshooting

### "CARBY_BOT_TOKEN not set"
```bash
echo $CARBY_BOT_TOKEN
# If empty, add to ~/.zshrc and reload
```

### "No module named 'telegram'"
```bash
pip3 install python-telegram-bot
```

### Bot not responding
1. Check bot is running: `ps aux | grep telegram_interface`
2. Check logs: `tail -f bot.log`
3. Verify token is correct

### Can't find bot in Telegram
- Search for the username you created (e.g., @carby_studio_bot)
- Make sure you saved the token correctly

---

## What the Bot Can Do

- 📋 **Projects** - List all active projects with status
- ➕ **New Project** - Start creating a project (manual for now)
- ⚙️ **More** - Credentials, system status, help
- **Approve stages** - When discover/design/build complete
- **Retry/Skip** - When stages fail
- **View logs** - Check agent output

---

## Next Steps

Once running:
1. Create a test project with Carby Studio
2. Watch for notifications when stages complete
3. Use buttons to approve and continue pipeline

Need help? Check logs or ask me!
