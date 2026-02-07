const ENDPOINT = "http://127.0.0.1:5055/v1/active_tab";

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  return tabs && tabs.length ? tabs[0] : null;
}

function isoUtcNow() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

async function sendActiveTab(reason) {
  try {
    const tab = await getActiveTab();
    if (!tab) return;

    // Some URLs (chrome://, about:) may be inaccessible; keep best-effort.
    const payload = {
      url: tab.url || null,
      title: tab.title || null,
      ts_utc: isoUtcNow(),
      reason,
    };

    await fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (_e) {
    // Silent: server may not be running.
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("tick", { periodInMinutes: 0.1667 }); // ~10s
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm && alarm.name === "tick") sendActiveTab("alarm");
});

chrome.tabs.onActivated.addListener(() => sendActiveTab("tabs.onActivated"));
chrome.tabs.onUpdated.addListener((_tabId, changeInfo) => {
  if (changeInfo.status === "complete") sendActiveTab("tabs.onUpdated.complete");
});
chrome.windows.onFocusChanged.addListener(() => sendActiveTab("windows.onFocusChanged"));
