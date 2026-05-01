from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, BigInteger, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime

Base = declarative_base()

class TradingSettings(Base):
    """
    جدول إعدادات التداول لكل مستخدم (نفس واجهة الصورة)
    """
    __tablename__ = "trading_settings"

    user_id = Column(BigInteger, ForeignKey("users.user_id"), primary_key=True)
    
    # مدخلات الاستراتيجية (نفس إعدادات الصورة)
    wave_filter = Column(Boolean, default=True)           # تفعيل فلتر الموجة السابقة
    fib_level = Column(Float, default=50.0)               # مستوى الفيبوناتشي %
    liquidity_sweep = Column(Boolean, default=True)       # قاعدة 1: سحب السيولة
    fvg_enabled = Column(Boolean, default=True)           # قاعدة 2: الفجوة السعرية (FVG)
    fvg_length = Column(Integer, default=10)              # الطول (10)
    multiplier = Column(Integer, default=1)               # المضاعف
    
    # إعدادات التداول
    signals_per_level = Column(Integer, default=2)        # عدد الإشارات لكل مستوى
    days_between_signals = Column(Integer, default=1)     # عدد الأيام بين الإشارات
    safe_zone_entry = Column(Boolean, default=False)      # الدخول من المنطقة الآمنة
    retracement_percent = Column(Float, default=50.0)     # نسبة تراجع السعر للدخول
    
    # إعدادات وقف الخسارة
    sl_mechanism = Column(String, default="auto")         # آلية وقف الخسارة (تلقائي/يدوي)
    stop_loss_percent = Column(Float, default=1.0)        # وقف الخسارة (%)
    
    # حالة البوت العامة للمستخدم
    is_bot_active = Column(Boolean, default=False)
    
    # العلاقة مع جدول المستخدمين
    user = relationship("User", back_populates="trading_settings")

class UserAPIKeys(Base):
    """
    جدول مفاتيح الـ API المشفرة لضمان الأمان
    """
    __tablename__ = "user_api_keys"

    user_id = Column(BigInteger, ForeignKey("users.user_id"), primary_key=True)
    exchange = Column(String)                             # اسم المنصة (Binance/Bybit)
    api_key_enc = Column(Text)                            # المفتاح مشفر
    api_secret_enc = Column(Text)                         # السر مشفر
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class TradeHistory(Base):
    """
    سجل الصفقات لمتابعة الأداء وإدارة القيود (عدد الإشارات لكل مستوى)
    """
    __tablename__ = "trade_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"))
    symbol = Column(String)                               # رمز الزوج (BTCUSDT)
    side = Column(String)                                 # (BUY/SELL)
    entry_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    status = Column(String)                               # (OPEN, CLOSED, CANCELLED)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

# ملاحظة: تأكد أن جدول User الحالي لديك يحتوي على تعريف relationship لـ trading_settings
