chrome.runtime.onInstalled.addListener(() => {
  if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
  }
});
chrome.action.onClicked.addListener(async (tab) => {
  if (chrome.sidePanel && tab && tab.windowId != null) {
    await chrome.sidePanel.open({ windowId: tab.windowId });
  }
});
chrome.runtime.onMessage.addListener((message, sender) => {
  if (message && message.type === 'OPEN_NETWORK_PANEL' && sender.tab && sender.tab.windowId != null) {
    chrome.sidePanel.open({ windowId: sender.tab.windowId }).catch(() => {});
  }
});
