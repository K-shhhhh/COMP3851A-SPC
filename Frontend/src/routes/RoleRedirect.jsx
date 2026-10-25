import { Navigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";
import UnsupportedRole from "./UnsupportedRole.jsx";

/** Single post-login entry point for every SPC account. */
export default function RoleRedirect() {
  const { isAuthenticated, isLoading, user } = useAuth();
  if (isLoading) return <div className="route-loading" role="status">Loading your session…</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (user?.role === "admin") return <Navigate to="/admin" replace />;
  if (user?.role === "student") return <Navigate to="/dashboard" replace />;
  return <UnsupportedRole />;
}
