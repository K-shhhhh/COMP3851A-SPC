/**
 * Build immutable frontend integration settings from Vite environment values.
 *
 * This configuration contains public browser addresses only. API keys and
 * other private credentials must remain in the backend environment.
 *
 * @param {Record<string, string | undefined>} [env={}] Vite environment values.
 * @param {{href: string}|null} [location=null] Browser location used to derive WebSocket URLs.
 * @returns {{apiBaseUrl: string, webSocketBaseUrl: string, useMocks: boolean, mockDelayMs: number}}
 *   Normalized, immutable integration settings.
 */
export function createIntegrationConfig(env = {}, location = null) {
  const apiBaseUrl = (env.VITE_API_BASE_URL || "/api/v1").replace(/\/+$/, "");
  let webSocketBaseUrl = env.VITE_WS_BASE_URL || "";

  if (!webSocketBaseUrl && location) {
    // Resolve both same-origin paths and explicit backend URLs before switching protocol.
    const url = new URL(apiBaseUrl, location.href);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    webSocketBaseUrl = url.href;
  }

  const delay = Number(env.VITE_MOCK_DELAY_MS ?? 800);
  return Object.freeze({
    apiBaseUrl,
    webSocketBaseUrl: webSocketBaseUrl.replace(/\/+$/, ""),
    // Only services that check this flag use mocks; it does not mock authentication.
    useMocks: env.VITE_USE_MOCKS === "true",
    mockDelayMs: Number.isFinite(delay) && delay >= 0 ? delay : 800,
  });
}

/** Shared integration settings used by frontend service modules. */
export const integrationConfig = createIntegrationConfig(
  import.meta.env || {},
  typeof window === "undefined" ? null : window.location,
);
