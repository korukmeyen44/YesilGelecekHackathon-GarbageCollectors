/* Apply before styles to avoid a bright flash in the installed driver app. */
try {
  const saved = localStorage.getItem('gc-theme');
  document.documentElement.dataset.theme = saved === 'dark' || saved === 'light' ? saved : matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
} catch { document.documentElement.dataset.theme = 'light'; }
