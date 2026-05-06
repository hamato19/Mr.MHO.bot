# keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
import config

def get_language_keyboard():
    """قائمة اختيار اللغة عند بداية التشغيل"""
    keyboard = [
        [
            InlineKeyboardButton("🇸🇦 العربية", callback_data='set_lang_ar'), 
            InlineKeyboardButton("🇺🇸 English", callback_data='set_lang_en')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def get_main_menu(uid, bot_username="bot"):
    """القائمة الرئيسية للبوت بعد التحديث"""
    kb = [
        [
            InlineKeyboardButton("👤 حسابي", callback_data='acc'), 
            InlineKeyboardButton("🔄 تجديد الاشتراك", callback_data='renew_sub') # تم إضافة الزر هنا
        ],
        [
            InlineKeyboardButton("📢 ربط قناة", callback_data='add_ch'),
            InlineKeyboardButton("📺 قنواتي", callback_data='view_chs')
        ],
        [
            InlineKeyboardButton("🌐 روابط الويب هوك", callback_data='view_wh'), 
            InlineKeyboardButton("🔄 تحديث الرمز", callback_data='gen_token')
        ],
        [
            InlineKeyboardButton("🤖 إضافة البوت كمشرف", url=f"https://t.me/{bot_username}?startchannel=true")
        ],
        [
            InlineKeyboardButton("☎️ الدعم الفني", url=config.SUPPORT_LINK)
        ]
    ]
    
    # إضافة زر لوحة التحكم للأدمن فقط
    if int(uid) == config.ADMIN_ID:
        kb.append([InlineKeyboardButton("👮 لوحة التحكم (الأدمن)", callback_data='admin_panel')])
        
    return InlineKeyboardMarkup(kb)

def get_channel_request_keyboard():
    """زر طلب مشاركة القناة (Reply Keyboard)"""
    kb = [
        [
            KeyboardButton(
                "📢 اختر القناة", 
                request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True)
            )
        ]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True)

def get_back_to_home():
    """زر العودة للقائمة الرئيسية"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة للقائمة الرئيسية", callback_data='home')]])

def get_admin_main_keyboard():
    """لوحة تحكم الأدمن الخاصة"""
    kb = [
        [InlineKeyboardButton("👥 قائمة المستخدمين", callback_data='admin_users')],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data='admin_stats')],
        [InlineKeyboardButton("🔑 توليد أكواد", callback_data='admin_generate_code')], # تم توحيد الـ callback
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='home')]
    ]
    return InlineKeyboardMarkup(kb)

def get_code_generation_keyboard():
    """أزرار اختيار مدة الكود المراد توليده"""
    kb = [
        [InlineKeyboardButton("📅 شهر (30 يوم)", callback_data='gen_days_30')],
        [InlineKeyboardButton("📅 3 أشهر (90 يوم)", callback_data='gen_days_90')],
        [InlineKeyboardButton("📅 سنة (365 يوم)", callback_data='gen_days_365')],
        [InlineKeyboardButton("🔙 عودة", callback_data='admin_panel')]
    ]
    return InlineKeyboardMarkup(kb)
