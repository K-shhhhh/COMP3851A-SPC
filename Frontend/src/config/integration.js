const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const configuredWebSocketUrl = import.meta.env.VITE_WS_BASE_URL || "";

function defaultWebSocketBaseUrl() {
  if (typeof window === "undefined") {
    return "";
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${apiBaseUrl}`;
}

export const integrationConfig = Object.freeze({
  apiBaseUrl: apiBaseUrl.replace(/\/$/, ""),
  webSocketBaseUrl: (configuredWebSocketUrl || defaultWebSocketBaseUrl()).replace(
    /\/$/,
    "",
  ),
  useMocks: import.meta.env.VITE_USE_MOCKS === "true",
  mockDelayMs: Number(import.meta.env.VITE_MOCK_DELAY_MS || 800),
});
