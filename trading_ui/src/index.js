import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

// هذا الملف هو حلقة الوصل بين كود React وصفحة الـ HTML
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
