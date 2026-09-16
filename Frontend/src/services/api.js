/** Legacy direct health-check helper retained during frontend integration. */

/**
 * Check whether the locally running backend reports a healthy response.
 *
 * @returns {Promise<object>} Parsed backend health response.
 * @throws {Error} When the health endpoint returns an unsuccessful status.
 */
export async function checkBackendHealth() {
  const response = await fetch("http://localhost:8000/health");

  if (!response.ok) {
    throw new Error("Backend health check failed");
  }

  return response.json();
}
