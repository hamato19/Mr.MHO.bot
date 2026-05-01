from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from . import models, security, database

app = FastAPI(title="MOH Trading API")

@app.post("/settings/update")
async def update_settings(user_id: int, settings_data: dict, db: Session = Depends(database.get_db)):
    """تحديث إعدادات الـ SMC والـ FVG للمستخدم"""
    db_settings = db.query(models.TradingSettings).filter(models.TradingSettings.user_id == user_id).first()
    if not db_settings:
        db_settings = models.TradingSettings(user_id=user_id)
        db.add(db_settings)
    
    # تحديث القيم ديناميكياً بناءً على ما يختاره المستخدم في الـ Mini App
    for key, value in settings_data.items():
        setattr(db_settings, key, value)
    
    db.commit()
    return {"status": "success", "message": "Settings updated"}

@app.post("/keys/save")
async def save_api_keys(user_id: int, api_key: str, secret: str, exchange: str, db: Session = Depends(database.get_db)):
    """حفظ مفاتيح المنصة مشفرة"""
    encrypted_key = security.encrypt_key(api_key)
    encrypted_secret = security.encrypt_key(secret)
    
    db_key = db.query(models.UserAPIKeys).filter(models.UserAPIKeys.user_id == user_id).first()
    if not db_key:
        db_key = models.UserAPIKeys(user_id=user_id)
        db.add(db_key)
        
    db_key.api_key_enc = encrypted_key
    db_key.api_secret_enc = encrypted_secret
    db_key.exchange = exchange
    
    db.commit()
    return {"status": "success", "message": "API Keys secured and saved"}
