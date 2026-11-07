// Only the packaged content script on X can ask to open a panel.
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== 'OPEN_NETWORK_PANEL' || !sender.tab ||
      !/^https:\/\/(x\.com|twitter\.com)\//.test(sender.url || '')) return;
  if (!chrome.sidePanel) { sendResponse({ ok: false }); return; }
  chrome.sidePanel.open({ windowId: sender.tab.windowId }).then(
    () => sendResponse({ ok: true }), () => sendResponse({ ok: false })
  );
  return true;
});
