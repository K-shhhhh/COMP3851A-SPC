import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { CheckCircle2, GraduationCap, MailCheck, Moon, ShieldCheck, Sun } from "lucide-react";
import { useTheme } from "../../contexts/ThemeContext.jsx";
import { confirmEmailVerification, resendEmailVerification } from "../../services/authService.js";
import {
  clearPendingVerification,
  readPendingVerification,
  rememberPendingVerification,
} from "../../utils/pendingVerification.js";
import "../../styles/styles.css";
import "./emailVerification.css";

const RESEND_COOLDOWN_SECONDS = 60; // Matches the current backend default; backend still enforces the limit.

function messageForVerificationError(error) {
  switch (error?.code) {
    case "INVALID_VERIFICATION_CODE":
      return "That code is incorrect or has already been used. Please try again.";
    case "VERIFICATION_CODE_EXPIRED":
      return "This code has expired or the maximum attempts were reached. Request a new code.";
    case "VERIFICATION_RESEND_TOO_SOON":
      return "Please wait before requesting another verification code.";
    case "VERIFICATION_DELIVERY_UNAVAILABLE":
      return "Email delivery is temporarily unavailable. Please try again later.";
    case "VALIDATION_ERROR":
      return "Please check your email address and the six-digit verification code.";
    default:
      return "We couldn't verify your email right now. Please try again.";
  }
}

export default function EmailVerificationPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const [email, setEmail] = useState(() =>
    location.state?.email || readPendingVerification()?.email || "",
  );
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendAt, setResendAt] = useState(() =>
    readPendingVerification()?.resendAvailableAt || 0,
  );
  const [now, setNow] = useState(Date.now);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, []);

  const cooldown = Math.max(0, Math.ceil((resendAt - now) / 1000));
  const address = email.trim();
  const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(address);
  const canConfirm = validEmail && /^\d{6}$/.test(code);

  function changeEmail(nextEmail) {
    setEmail(nextEmail);
    setCode("");
    setError("");
    setNotice("");
    const previous = readPendingVerification();
    if (nextEmail.trim().toLowerCase() !== previous?.email) {
      // A different account must not inherit another account's cooldown.
      setResendAt(0);
    } else {
      setResendAt(previous?.resendAvailableAt || 0);
    }
  }

  async function confirmCode(event) {
    event.preventDefault();
    if (!canConfirm || busy || resending) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await confirmEmailVerification({ email: address, code });
      if (result?.verified !== true) {
        setError("We couldn't confirm verification. Please try again.");
        return;
      }
      clearPendingVerification();
      navigate("/login", {
        replace: true,
        state: { notice: "Email verified successfully. You can now sign in." },
      });
    } catch (caught) {
      setError(messageForVerificationError(caught));
    } finally {
      setBusy(false);
    }
  }

  async function resendCode() {
    if (!validEmail || cooldown > 0 || busy || resending) return;
    setResending(true);
    setError("");
    setNotice("");
    try {
      await resendEmailVerification({ email: address });
      const pending = rememberPendingVerification(address, {
        expiresIn: null, // Resend creates a fresh code; the endpoint provides no TTL.
        cooldownSeconds: RESEND_COOLDOWN_SECONDS,
      });
      setResendAt(pending?.resendAvailableAt || 0);
      setCode("");
      setNow(Date.now());
      setNotice("If this account is awaiting verification, a new code has been sent.");
    } catch (caught) {
      setError(messageForVerificationError(caught));
      if (caught?.code === "VERIFICATION_RESEND_TOO_SOON") {
        const pending = rememberPendingVerification(address, {
          cooldownSeconds: RESEND_COOLDOWN_SECONDS,
        });
        setResendAt(pending?.resendAvailableAt || 0);
        setNow(Date.now());
      }
    } finally {
      setResending(false);
    }
  }

  return (
    <div className="auth-layout">
      <section className="auth-hero">
        <div className="auth-hero-content verification-hero-content">
          <div className="auth-brand">
            <div className="auth-brand-icon"><GraduationCap size={28} /></div>
            <div><strong>Smart Peer</strong><span>Companion</span></div>
          </div>
          <div className="auth-hero-copy">
            <h1>One more step to start studying.</h1>
            <p>Verify your university email to keep the SPC community secure and connected.</p>
          </div>
          <div className="verification-hero-note">
            <ShieldCheck size={24} aria-hidden="true" />
            <span>Only verified accounts can access their study space.</span>
          </div>
        </div>
      </section>

      <section className="auth-form-section">
        <button
          type="button"
          className="auth-theme-toggle"
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? <Sun size={19} /> : <Moon size={19} />}
        </button>
        <div className="auth-form-wrapper">
          <div className="auth-mobile-brand"><GraduationCap size={25} /><strong>Smart Peer Companion</strong></div>
          <div className="verification-symbol"><MailCheck size={31} aria-hidden="true" /></div>
          <div className="auth-form-heading">
            <h2>Verify your email</h2>
            <p>Enter the six-digit code sent to your email address. Check your inbox and spam folder.</p>
          </div>
          <form className="auth-form" onSubmit={confirmCode}>
            <div className="auth-field">
              <label htmlFor="verification-email">Email address</label>
              <input
                id="verification-email"
                type="email"
                value={email}
                onChange={(event) => changeEmail(event.target.value)}
                autoComplete="email"
                placeholder="student@uon.edu.au"
                disabled={busy || resending}
                required
              />
              <p className="auth-field-help">This should be the address you registered with.</p>
            </div>
            <div className="auth-field">
              <label htmlFor="verification-code">Six-digit verification code</label>
              <input
                id="verification-code"
                className="verification-code-input"
                type="text"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                autoComplete="one-time-code"
                placeholder="000000"
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                disabled={busy || resending}
                aria-describedby="verification-code-hint"
                required
                autoFocus
              />
              <p className="auth-field-help" id="verification-code-hint">The code expires after a limited time and can be used only once.</p>
            </div>
            {error && <div className="auth-error" role="alert">{error}</div>}
            {notice && <div className="auth-success" role="status"><CheckCircle2 size={17} aria-hidden="true" />{notice}</div>}
            <button type="submit" className="auth-primary-button" disabled={!canConfirm || busy || resending}>
              {busy ? "Verifying…" : "Verify email"}
            </button>
          </form>
          <div className="verification-resend">
            <p>Didn't receive the email?</p>
            <button
              type="button"
              className="auth-link-button"
              onClick={resendCode}
              disabled={!validEmail || cooldown > 0 || busy || resending}
            >
              {resending ? "Sending…" : cooldown > 0 ? `Resend code in ${cooldown}s` : "Resend code"}
            </button>
          </div>
          <p className="auth-switch">
            <button type="button" onClick={() => navigate("/login")}>Back to sign in</button>
          </p>
        </div>
      </section>
    </div>
  );
}
