# keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
from telegram.constants import ParseMode
import os

ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

async def get_main_menu(uid, bot_username):
    """القائمة الرئيسية للمستخدم"""
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("📢 ربط قناة", callback_data='add_ch')],
        [InlineKeyboardButton("🌐 روابط الويب هوك", callback_data='view_wh'), InlineKeyboardButton("🔄 تحديث الرمز", callback_data='gen_token')],
        [InlineKeyboardButton("📺 قنواتي المرتبطة", callback_data='view_chs')],
        [InlineKeyboardButton("🤖 إضافة البوت كمشرف", url=f"https://t.me/{bot_username}?startchannel=true")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=f"tg://user?id={ADMIN_ID}")]
    ]
    if int(uid) == ADMIN_ID:
        kb.append([InlineKeyboardButton("👮 لوحة التحكم (الأدمن)", callback_data='admin_panel')])
    return InlineKeyboardMarkup(kb)

def get_language_keyboard():
    """قائمة اختيار اللغة"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇸🇦 العربية", callback_data='set_lang_ar'), 
         InlineKeyboardButton("🇺🇸 English", callback_data='set_lang_en')]
    ])

def get_channel_request_keyboard():
    """زر طلب قناة (الموجود في لوحة المفاتيح)"""
    kb = [[KeyboardButton("📢 اختر القناة", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))]]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True)

def get_back_to_home():
    """زر العودة للقائمة الرئيسية"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة", callback_data='home')]])
