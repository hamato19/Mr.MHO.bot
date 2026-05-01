import React, { useEffect } from 'react';
import Header from './components/Header';
import SettingsForm from './components/SettingsForm';
import './index.css';

function App() {
  useEffect(() => {
    const tg = window.Telegram.WebApp;
    if (tg) {
      tg.ready();
      tg.expand(); // لفتح التطبيق بكامل الشاشة
      tg.setHeaderColor('#000000'); // لون شريط التليجرام العلوي
    }
  }, []);

  return (
    <div className="min-h-screen bg-black text-white p-4 font-sans">
      <Header />
      <SettingsForm />
      <div className="text-center mt-6">
        <button 
          onClick={() => window.Telegram.WebApp.close()}
          className="text-[10px] text-gray-500 uppercase tracking-widest border border-gray-800 px-4 py-1 rounded-full"
        >
          اغلاق التطبيق
        </button>
      </div>
    </div>
  );
}

export default App;
