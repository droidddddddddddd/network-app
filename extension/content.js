(() => {
  if (document.getElementById('network-overlay-launcher')) return;
  const host = document.createElement('div');
  host.id = 'network-overlay-launcher';
  host.style.cssText = 'position:fixed;right:18px;bottom:96px;z-index:2147483647';
  const shadow = host.attachShadow({ mode: 'closed' });
  const style = document.createElement('style');
  style.textContent = `button{border:1px solid #2af08c;background:#09130f;color:#eafff3;border-radius:999px;padding:12px 16px;font:700 13px system-ui;box-shadow:0 8px 28px #0008;cursor:pointer}button:hover{background:#10251a}span{color:#2af08c;margin-right:7px}`;
  const button = document.createElement('button');
  button.type = 'button';
  button.innerHTML = '<span>◉</span> NETWORK';
  button.title = 'Open NETWORK beside X';
  button.addEventListener('click', () => chrome.runtime.sendMessage({ type: 'OPEN_NETWORK_PANEL' }));
  shadow.append(style, button);
  document.documentElement.appendChild(host);
})();
