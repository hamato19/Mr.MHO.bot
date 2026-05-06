import logging
import asyncio
import datetime
import secrets
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from database import get_db
from psycopg2.extras import RealDictCursor

# --- 1. القائمة الرئيسية للأدمن ---
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    kb = [
        [InlineKeyboardButton("🎫 توليد أكواد تفعيل", callback_data='admin_generate_code')],
        [InlineKeyboardButton("👥 قائمة المستخدمين", callback_data='admin_users'),
         InlineKeyboardButton("🔍 إحصائيات النظام", callback_data='admin_stats')],
        [InlineKeyboardButton("📢 إذاعة (Broadcast)", callback_data='admin_broadcast')],
        [InlineKeyboardButton("🏠 عودة للقائمة الرئيسية", callback_data='home')]
    ]
    
    text = "👮 <b>لوحة تحكم المطور (أبو إلياس)</b>\n\nإدارة المستخدمين والاشتراكات والبيانات:"
    
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    else:
        await update.effective_chat.send_message(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

# --- 2. نظام توليد الأكواد (محدث بالمدد الجديدة) ---
async def show_generate_code_menu(update: Update):
    query = update.callback_query
    kb = [
        [InlineKeyboardButton("📅 شهر (30 يوم)", callback_data='gen_days_30'),
         InlineKeyboardButton("📆 شهرين (60 يوم)", callback_data='gen_days_60')],
        [InlineKeyboardButton("🗓️ 3 أشهر (90 يوم)", callback_data='gen_days_90'),
         InlineKeyboardButton("🌟 سنة (365 يوم)", callback_data='gen_days_365')],
        [InlineKeyboardButton("🔑 كود تجريبي (يوم واحد)", callback_data='gen_days_1')],
        [InlineKeyboardButton("🔙 عودة للوحة الأدمن", callback_data='admin_panel')]
    ]
    text = "🎫 <b>توليد كود تفعيل جديد:</b>\n\nاختر مدة الصلاحية للكود الذي تريد إنشاؤه:"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def process_generate_code(update: Update, days: int):
    query = update.callback_query
    # توليد كود احترافي يبدأ بـ MHO
    new_code = f"MHO-{secrets.token_hex(4).upper()}"
    
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO codes (code, duration_days, is_used, created_at) VALUES (%s, %s, False, NOW())",
                    (new_code, days)
                )
                conn.commit()
        
        text = (f"✅ <b>تم توليد الكود بنجاح!</b>\n\n"
                f"🎫 الكود: <code>{new_code}</code>\n"
                f"⏳ المدة: {days} يوم\n\n"
                f"أرسل الكود للمستخدم لتفعيل حسابه.")
        
        kb = [[InlineKeyboardButton("🔄 توليد كود آخر", callback_data='admin_generate_code')],
              [InlineKeyboardButton("🔙 عودة للوحة", callback_data='admin_panel')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Generate Code Error: {e}")
        await query.answer("❌ خطأ في قاعدة البيانات.")

# --- 3. إدارة المستخدمين ---
async def list_users(update: Update):
    query = update.callback_query
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT user_id, is_activated FROM users ORDER BY created_at DESC LIMIT 15")
                users = cur.fetchall()
        
        text = "👥 <b>آخر 15 مستخدم مسجل:</b>\n\n"
        kb = []
        for u in users:
            status = "✅" if u['is_activated'] else "❌"
            text += f"• <code>{u['user_id']}</code> {status}\n"
            kb.append([InlineKeyboardButton(f"⚙️ إدارة {u['user_id']}", callback_data=f"manage_user_{u['user_id']}")])
        
        kb.append([InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"List Users Error: {e}")

async def manage_single_user(update: Update, user_id: str):
    query = update.callback_query
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                user = cur.fetchone()
        
        if not user: return await query.answer("❌ مستخدم غير موجود")

        status_txt = "نشط ✅" if user['is_activated'] else "غير مفعل ❌"
        expiry = user['expiry_date'].strftime('%Y-%m-%d') if user['expiry_date'] else "غير محدد"
        
        text = (f"👤 <b>إدارة المستخدم:</b> <code>{user_id}</code>\n\n"
                f"• الحالة: {status_txt}\n"
                f"• ينتهي في: <code>{expiry}</code>\n"
                f"• الرمز السري: <code>{user['secret_token']}</code>")
        
        kb = [
            [InlineKeyboardButton("✅ تفعيل 30 يوم", callback_data=f"adm_act_{user_id}"),
             InlineKeyboardButton("🚫 تعطيل", callback_data=f"adm_deact_{user_id}")],
            [InlineKeyboardButton("🗑️ حذف نهائي", callback_data=f"adm_del_{user_id}")],
            [InlineKeyboardButton("🔙 عودة", callback_data='admin_users')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    except Exception as e: logging.error(e)

async def update_user_status(update: Update, action: str, user_id: str):
    query = update.callback_query
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                if action == 'activate':
                    new_expiry = datetime.datetime.now() + datetime.timedelta(days=30)
                    cur.execute("UPDATE users SET is_activated = True, expiry_date = %s WHERE user_id = %s", (new_expiry, user_id))
                    msg = "✅ تم التفعيل"
                elif action == 'deactivate':
                    cur.execute("UPDATE users SET is_activated = False WHERE user_id = %s", (user_id,))
                    msg = "❌ تم التعطيل"
                elif action == 'delete':
                    cur.execute("DELETE FROM entities WHERE user_id = %s", (user_id,))
                    cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
                    msg = "🗑️ تم الحذف"
                conn.commit()
        await query.answer(msg, show_alert=True)
        await list_users(update)
    except Exception as e: logging.error(e)

# --- 4. الإحصائيات والإذاعة ---
async def show_admin_stats(update: Update):
    query = update.callback_query
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM users WHERE is_activated = True")
            active = cur.fetchone()[0]
    
    text = f"📊 <b>إحصائيات نظام Mr.MHO:</b>\n\n• إجمالي المستخدمين: {total}\n• المشتركين النشطين: {active}"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')]]), parse_mode=ParseMode.HTML)

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = 'WAIT_BROADCAST_MSG'
    await update.callback_query.edit_message_text("📢 أرسل رسالة الإذاعة الآن (نص أو صورة):", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data='admin_panel')]]))

async def exec_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM users")
            users = cur.fetchall()
    
    count = 0
    status_msg = await msg.reply_text(f"⏳ جاري الإرسال...")
    for u in users:
        try:
            await context.bot.copy_message(chat_id=u[0], from_chat_id=msg.chat_id, message_id=msg.message_id)
            count += 1
            await asyncio.sleep(0.05)
        except: continue
    await status_msg.edit_text(f"✅ تم الإرسال إلى {count} مستخدم.")
    context.user_data['state'] = None
