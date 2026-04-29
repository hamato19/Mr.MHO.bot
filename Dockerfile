# 1. تحديد نظام التشغيل الأساسي (بايثون)
FROM python:3.11-slim

# 2. تثبيت ملفات النظام (التي كتبتها أنت في الصورة ولكن هنا مكانها الصحيح)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 3. تحديد مكان الكود داخل السيرفر
WORKDIR /app

# 4. نسخ وتثبيت المكتبات البرمجية
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. نسخ باقي ملفات البوت
COPY . .

# 6. أمر تشغيل البوت (تأكد أن الملف الأساسي عندك اسمه main.py)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
