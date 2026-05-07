# keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
import config

def get_language_keyboard():
    return InlineKeyboardMarkup([[ 
        InlineKeyboardButton("🇸🇦 العربية", callback_data='set_ar'), 
        InlineKeyboardButton("🇺🇸 English", callback_data='set_en') 
    ]])

async def get_main_menu(uid, bot_username="bot"):
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🔄 تجديد الاشتراك", callback_data='ren')],
        [InlineKeyboardButton("📢 ربط قناة", callback_data='add'), InlineKeyboardButton("📺 قنواتي", callback_data='chs')],
        [InlineKeyboardButton("🌐 الويب هوك", callback_data='wh'), InlineKeyboardButton("🔄 تحديث الرمز", callback_data='tok')],
        [InlineKeyboardButton("🤖 إضافة البوت كمشرف", url=f"https://t.me/{bot_username}?startchannel=true")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=config.SUPPORT_LINK)]
    ]
    if int(uid) == config.ADMIN_ID:
        kb.append([InlineKeyboardButton("👮 لوحة الأدمن", callback_data='adm')])
    return InlineKeyboardMarkup(kb)

def get_entities_keyboard(entities):
    keyboard = []
    for ent in entities:
        try:
            # استخدام 'dl_' بدلاً من 'del_ent_' لتوفير مساحة وتجنب خطأ Button_data_invalid
            eid = str(ent[0]) if isinstance(ent, (tuple, list)) else str(ent)
            name = str(ent[1]) if isinstance(ent, (tuple, list)) else "قناة"
            keyboard.append([InlineKeyboardButton(f"❌ {name}", callback_data=f"dl_{eid}")])
        except: continue
    keyboard.append([InlineKeyboardButton("🏠 عودة", callback_data='home')])
    return InlineKeyboardMarkup(keyboard)

def get_back_to_home():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')]])

def get_admin_main_keyboard():
    kb = [[InlineKeyboardButton("👥 المستخدمين", callback_data='adm_u')],
          [InlineKeyboardButton("📊 الإحصائيات", callback_data='adm_s')],
          [InlineKeyboardButton("🔑 توليد أكواد", callback_data='adm_g')],
          [InlineKeyboardButton("🏠 الرئيسية", callback_data='home')]]
    return InlineKeyboardMarkup(kb)

def get_channel_request_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("📢 اختر القناة", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))]], resize_keyboard=True, one_time_keyboard=True)
