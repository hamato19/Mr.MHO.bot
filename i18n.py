# i18n.py
STRINGS = {
    'ar': {
        'welcome': "🚀 مرحباً بك {name} في نظام سمو الأرقام",
        'accept_msg': "✅ تم تسجيل موافقتك بنجاح.",
        'decline_msg': "🚫 نعتذر، لا يمكن استخدام البوت دون الموافقة على الشروط.",
        'wait_code': "⚠️ الوصول مقيد. يرجى إرسال **كود التفعيل**:",
    },
    'en': {
        'welcome': "🚀 Welcome {name} to Sumou Al-Arqam System",
        'accept_msg': "✅ Your agreement has been successfully recorded.",
        'decline_msg': "🚫 Sorry, the bot cannot be used without agreeing to the terms.",
        'wait_code': "⚠️ Access restricted. Please send your **activation code**:",
    }
}

def get_text(key, lang='ar', **kwargs):
    # يحاول جلب النص باللغة المختارة، وإذا لم يجدها يعود للعربية كافتراضي
    text = STRINGS.get(lang, STRINGS['ar']).get(key, f"[{key}]")
    return text.format(**kwargs)
        'success_act': "✅ Activation successful for {days} days!",
        'spam_alert': "⛔️ <b>Action Blocked:</b> Rate limit exceeded.",
        'banned_msg': "🚫 <b>Access Denied:</b> Your account is permanently banned.",
        'db_error': "❌ Sorry, database connection error.",
        'home_btn': "🏠 Main Menu",
        'back_btn': "🔙 Back",
        'admin_panel': "👮 Admin Control Panel",
    }
}

def get_text(key, lang='ar', **kwargs):
    """دالة جلب النص بناءً على مفتاح اللغة"""
    try:
        text = STRINGS.get(lang, STRINGS['ar']).get(key, f"Missing Key: {key}")
        return text.format(**kwargs) if kwargs else text
    except Exception as e:
        return f"Error text: {key}"
