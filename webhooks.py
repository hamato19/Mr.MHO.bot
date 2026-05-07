import os, requests, secrets
from flask import Flask, request, jsonify
from database import get_db
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import config, services, keyboards

app = Flask(__name__)
BOT_TOKEN = config.BOT_TOKEN

# --- 1. سيرفر Flask (استقبال الإشارات خام 100%) ---
@app.route('/webhook/<token>/<target_id>', methods=['POST'])
def tv_webhook(token, target_id):
    # استقبال الإشارة كـ نص خام
    raw_data = request.get_data(as_text=True)
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT u.user_id FROM users u JOIN entities e ON u.user_id = e.user_id 
                           WHERE u.secret_token=%s AND e.entity_id=%s AND u.is_activated=TRUE""", (token, target_id))
            if not cur.fetchone(): return jsonify({"error": "Unauthorized"}), 403
    
    # إرسال الإشارة (بدون ParseMode) لضمان عدم تعارض الرموز مثل < >
    payload = {"chat_id": target_id, "text": raw_data}
    
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload, timeout=5)
        return jsonify({"status": "sent"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

# --- 2. وظائف البوت (واجهة المستخدم) ---
async def show_webhook_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user, ents = services.get_user_data(uid), services.get_user_entities(uid)
    
    if not ents:
        return await update.callback_query.edit_message_text("⚠️ <b>اربط قناة أولاً!</b>", 
            parse_mode=ParseMode.HTML, reply_markup=keyboards.get_back_to_home())
    
    base_url = getattr(config, 'WEBHOOK_BASE_URL', 'https://servernet.ct.ws')
    msg = "🌐 <b>روابط الويب هوك:</b>\n\n"
    for e in ents:
        msg += f"📺 قناة: <code>{e['entity_id']}</code>\n🔗 <code>{base_url}/webhook/{user['secret_token']}/{e['entity_id']}</code>\n\n"
    
    await update.callback_query.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=keyboards.get_back_to_home())

async def refresh_secret_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_token = secrets.token_hex(8)
    services.update_user_token(update.effective_user.id, new_token)
    await update.callback_query.answer("🔄 تم تحديث الرمز بنجاح", show_alert=True)
    await show_webhook_links(update, context)

def run_server():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
