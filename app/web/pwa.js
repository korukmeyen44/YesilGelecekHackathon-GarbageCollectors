"use strict";
const GCPWA = (() => {
  let promptEvent, registration, driving = false, refreshing = false;
  const themeButton = document.querySelector('#themeToggle');
  function theme(value, persist = false) {
    document.documentElement.dataset.theme = value;
    if(persist) try { localStorage.setItem('gc-theme',value); } catch { /* Private mode may disable storage. */ }
    const dark = value === 'dark';
    themeButton.setAttribute('aria-pressed',String(dark));
    themeButton.setAttribute('aria-label',dark ? 'Açık temaya geç' : 'Koyu temaya geç');
    themeButton.title = dark ? 'Açık tema' : 'Koyu tema';
    themeButton.querySelector('use').setAttribute('href',dark ? '#i-sun' : '#i-moon');
    document.querySelector('meta[name="theme-color"]').content = dark ? '#0d202c' : '#f3f6fa';
  }
  theme(document.documentElement.dataset.theme || 'light');
  themeButton.addEventListener('click',()=>theme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark',true));
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change',event=>{
    try{if(!localStorage.getItem('gc-theme'))theme(event.matches?'dark':'light');}catch{}
  });
  window.addEventListener('beforeinstallprompt',event => { event.preventDefault(); promptEvent = event; document.querySelector('#installButton').classList.add('install-ready'); });
  const standalone = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  function showInstall() {
    const status = document.querySelector('#installStatus');
    status.textContent = !window.isSecureContext ? 'Telefon kurulumu ve canlı GPS için uygulamayı HTTPS adresinden açın. Bu yerel HTTP adresi tarayıcıda kullanılabilir.' : standalone() ? 'Uygulama zaten cihazınızda bağımsız olarak açık.' : /iphone|ipad|ipod/i.test(navigator.userAgent) ? 'Safari’de Paylaş → Ana Ekrana Ekle yolunu izleyin.' : 'Tarayıcı menüsünden “Uygulamayı yükle” veya “Ana ekrana ekle” seçeneğini kullanın.';
    document.querySelector('#installDialog').showModal();
  }
  document.querySelector('#installButton').addEventListener('click',async () => {
    if(!promptEvent) return showInstall();
    const event = promptEvent; promptEvent = null;
    try { await event.prompt(); await event.userChoice; } catch { showInstall(); }
  });
  window.addEventListener('appinstalled',()=>{ promptEvent = null; document.querySelector('#installButton').hidden = true; });
  if(standalone()) document.querySelector('#installButton').hidden = true;
  function showUpdate() {
    if(!registration?.waiting) return;
    document.querySelector('#updateBanner').hidden = false;
    const button = document.querySelector('#applyUpdate');
    button.disabled = driving;
    button.textContent = driving ? 'Seferden sonra' : 'Yenile';
  }
  document.querySelector('#applyUpdate').addEventListener('click',()=> {
    if(driving || !registration?.waiting) return;
    refreshing = true; registration.waiting.postMessage({type:'ACTIVATE_UPDATE'});
  });
  if('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.addEventListener('controllerchange',()=>{ if(refreshing) location.reload(); });
    window.addEventListener('load',async()=> {
      try {
        registration = await navigator.serviceWorker.register('/sw.js',{scope:'/',updateViaCache:'none'});
        showUpdate();
        registration.addEventListener('updatefound',()=> {
          const worker = registration.installing;
          worker?.addEventListener('statechange',()=>{ if(worker.state === 'installed' && navigator.serviceWorker.controller) showUpdate(); });
        });
      } catch { document.querySelector('#installStatus').textContent = 'Çevrimdışı hazırlık tamamlanamadı. Bağlantı varken yeniden açın.'; }
    });
  }
  // Last unprotected dashboard only. Tokens and authenticated API responses are never persisted.
  async function snapshot(mode, value) {
    if(!('indexedDB' in window)) return null;
    return new Promise(resolve => {
      const opening = indexedDB.open('gc-device-v1',1);
      opening.onupgradeneeded = () => opening.result.createObjectStore('snapshots');
      opening.onerror = () => resolve(null);
      opening.onblocked = () => resolve(null);
      opening.onsuccess = () => {
        const db = opening.result, tx = db.transaction('snapshots',mode === 'get' ? 'readonly' : 'readwrite');
        const store = tx.objectStore('snapshots');
        const request = mode === 'get' ? store.get('dashboard') : mode === 'delete' ? store.delete('dashboard') : store.put(value,'dashboard');
        let result = null;
        request.onsuccess = () => { result = request.result || null; };
        tx.oncomplete = () => { db.close(); resolve(result); };
        tx.onerror = tx.onabort = () => { db.close(); resolve(null); };
      };
    }).catch(()=>null);
  }
  return {theme, snapshot, setDriving(value) { driving = value; showUpdate(); }};
})();
window.GCPWA = GCPWA;
