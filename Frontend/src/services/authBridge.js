/** The HTTP client talks to the current AuthProvider without importing React. */
let bridge = null;

export function configureAuthBridge(handlers) {
  bridge = handlers;
  return () => {
    if (bridge === handlers) bridge = null;
  };
}

export function getAuthBridge() {
  return bridge;
}
