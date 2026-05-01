import React, { useEffect } from 'react';
import Header from './components/Header';
import SettingsForm from './components/SettingsForm';
import ApiKeys from './components/ApiKeys';

function App() {
  useEffect(() => {
    // تهيئة واجهة تليجرام
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand(); // تمديد التطبيق لكامل الشاشة
    tg.MainButton.setText("حفظ وتشغيل البوت").show();
    tg.MainButton.onClick(() => {
        tg.showConfirm("هل تريد حفظ الإعدادات وتفعيل التداول الآلي؟");
    });
  }, []);

  return (
    <div className="max-w-md mx-auto min-h-screen flex flex-col pb-20">
      <Header />
      <div className="flex-grow overflow-y-auto">
        <SettingsForm />
        <ApiKeys />
      </div>
      <div className="text-center p-4 text-[9px] text-gray-600 uppercase tracking-widest">
        Powered by Aram System & MOH Signals
      </div>
    </div>
  );
}

export default App;
