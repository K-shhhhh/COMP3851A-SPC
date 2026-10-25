import { apiRequest } from "./apiClient.js";

export function register({
  fullName,
  email,
  password,
}) {
  return apiRequest("/auth/register", {
    method: "POST",
    body: JSON.stringify({
      full_name: fullName,
      email,
      password,
    }),
  });
}

export function login({
  email,
  password,
}) {
  return apiRequest("/auth/login", {
    method: "POST",
    credentials: "include",
    body: JSON.stringify({
      email,
      password,
    }),
  });
}

export function getCurrentUser(accessToken) {
  return apiRequest("/auth/me", {
    method: "GET",
    accessToken,
  });
}

export function refreshSession() {
  return apiRequest("/auth/refresh", {
    method: "POST",
    credentials: "include",
    skipAuthHandling: true,
    skipAuthRefresh: true,
  });
}

export function logout(accessToken) {
  return apiRequest("/auth/logout", {
    method: "POST",
    // When idle, omit Authorization and let the HttpOnly cookie revoke session.
    ...(accessToken ? { accessToken } : {}),
    credentials: "include",
    skipAuthHandling: true,
    skipAuthRefresh: true,
  });
}

export function createWebSocketTicket(accessToken) {
  return apiRequest("/auth/websocket-ticket", {
    method: "POST",
    accessToken,
  });
}