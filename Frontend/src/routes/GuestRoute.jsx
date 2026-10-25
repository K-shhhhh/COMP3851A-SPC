import { useAuth } from "../contexts/AuthContext.jsx";
import RoleRedirect from "./RoleRedirect.jsx";

export default function GuestRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="route-loading" role="status">Loading your session…</div>;
  return isAuthenticated ? <RoleRedirect /> : children;
}
