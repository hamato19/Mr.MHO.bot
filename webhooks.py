# webhooks.py
import os
import requests
from flask import Flask, request, jsonify
from database import get_db

app = Flask(__name__)
BOT_TOKEN = os.getenv('BOT_TOKEN')

@app.route('/')
def index(): 
    return "🚀 Sumou Webhook Server Online", 200

@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def tv_webhook(token, target_id):
    raw_data = request.get_data(as_text=True)
    
    with get_db() as conn:
        with conn.cursor() as cur:
            # التحقق من الرمز وتفعيل المستخدم
            cur.execute("""
                SELECT u.user_id FROM users u 
                JOIN entities e ON u.user_id = e.user_id 
                WHERE u.secret_token=%s AND e.entity_id=%s AND u.is_activated=TRUE
            """, (token, target_id))
            
            if not cur.fetchone():
                return jsonify({"error": "Unauthorized or Inactive"}), 403
    
    # إرسال التنبيه للقناة عبر التلجرام
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": target_id, 
        "text": raw_data, 
        "parse_mode": "HTML" # خليته HTML عشان لو تبي تنسق رسائل TradingView
    }
    
    try:
        requests.post(url, json=payload, timeout=5)
        return jsonify({"status": "sent"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def run_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
