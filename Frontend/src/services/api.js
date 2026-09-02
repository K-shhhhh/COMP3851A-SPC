// services/api.js

export async function checkBackendHealth() {
  const response = await fetch("http://localhost:8000/health");

  if (!response.ok) {
    throw new Error("Backend health check failed");
  }

  return response.json();
}