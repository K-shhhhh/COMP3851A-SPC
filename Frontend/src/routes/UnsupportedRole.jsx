import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";

/** Explicit deny state for accounts with an unrecognized role. */
export default function UnsupportedRole() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [working, setWorking] = useState(false);
  async function signOut() {
    setWorking(true);
    try { await logout(); navigate("/login", { replace: true }); }
    finally { setWorking(false); }
  }
  return (
    <main style={{ maxWidth: 520, padding: "60px 24px", margin: "auto" }}>
      <h1 style={{ fontSize: 26 }}>Account role is not supported</h1>
      <p>Please contact the SPC team about access to this account.</p>
      <button disabled={working} type="button" onClick={signOut}>
        {working ? "Signing out…" : "Sign out"}
      </button>
    </main>
  );
}
