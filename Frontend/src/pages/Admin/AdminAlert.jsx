import { AlertTriangle } from "lucide-react";

export default function AdminAlert({ error, retry }) {
  if (!error) return null;
  const notConfigured = error.code === "PERSISTENCE_NOT_CONFIGURED";
  const message = notConfigured
    ? "The administration database adapter is not connected yet. The backend returns 503, so live data cannot be displayed."
    : error.status === 403
      ? "Your account does not have permission to read this administrative resource."
      : error.message || "Unable to load administration data.";
  return (
    <div className="admin-alert" role="alert">
      <AlertTriangle size={21} />
      <div><strong>{notConfigured ? "Backend integration required" : "Unable to load data"}</strong><p>{message}</p>{error.requestId && <small>Request ID: {error.requestId}</small>}</div>
      {!notConfigured && retry && <button className="admin-button admin-button-outline" onClick={retry} type="button">Retry</button>}
    </div>
  );
}
