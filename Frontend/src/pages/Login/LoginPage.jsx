import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bot,
  BrainCircuit,
  Eye,
  EyeOff,
  GraduationCap,
  Users,
} from "lucide-react";

import { useAuth } from "../../contexts/AuthContext.jsx";
import "../../styles/styles.css";

function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    setError("");

    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }

    try {
      setIsSubmitting(true);

      await login({
        email: email.trim(),
        password,
      });

      navigate("/dashboard");
    } catch (err) {
      if (err.code === "INVALID_CREDENTIALS") {
        setError("Incorrect email or password.");
      } else if (err.code === "ACCOUNT_INACTIVE") {
        setError("Your account is currently inactive.");
      } else if (err.code === "VALIDATION_ERROR") {
        setError("Please check your login details.");
      } else {
        setError("Unable to sign in. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-layout">
      <section className="auth-hero">
        <div className="auth-hero-content">
          <div className="auth-brand">
            <div className="auth-brand-icon">
              <GraduationCap size={28} />
            </div>

            <div>
              <strong>Smart Peer</strong>
              <span>Companion</span>
            </div>
          </div>

          <div className="auth-hero-copy">
            <h1>Study smarter, together.</h1>

            <p>
              Your intelligent learning companion that transforms lecture
              notes into interactive study experiences.
            </p>
          </div>

          <div className="auth-features">
            <div className="auth-feature">
              <div className="auth-feature-icon">
                <Bot size={21} />
              </div>

              <div>
                <strong>AI Study Assistant</strong>
                <span>
                  Ask questions and understand difficult concepts faster.
                </span>
              </div>
            </div>

            <div className="auth-feature">
              <div className="auth-feature-icon">
                <Users size={21} />
              </div>

              <div>
                <strong>Collaborative Study Groups</strong>
                <span>
                  Learn together and share knowledge with classmates.
                </span>
              </div>
            </div>

            <div className="auth-feature">
              <div className="auth-feature-icon">
                <BrainCircuit size={21} />
              </div>

              <div>
                <strong>Knowledge Graphs</strong>
                <span>
                  Turn your notes into connected concepts and learning paths.
                </span>
              </div>
            </div>
          </div>

          <div className="auth-quote">
            <p>
              “SPC completely changed the way I prepare for exams. Everything I
              need is finally in one place.”
            </p>

            <span>— University Student</span>
          </div>
        </div>
      </section>

      <section className="auth-form-section">
        <div className="auth-form-wrapper">
          <div className="auth-mobile-brand">
            <GraduationCap size={25} />
            <strong>Smart Peer Companion</strong>
          </div>

          <div className="auth-form-heading">
            <h2>Welcome back</h2>
            <p>Enter your details to continue to Smart Peer Companion.</p>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="auth-field">
              <label htmlFor="login-email">University Email</label>

              <input
                id="login-email"
                type="email"
                placeholder="you@university.edu"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
              />
            </div>

            <div className="auth-field">
              <label htmlFor="login-password">Password</label>

              <div className="auth-password-field">
                <input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                />

                <button
                  type="button"
                  className="auth-password-toggle"
                  onClick={() => setShowPassword((current) => !current)}
                  aria-label={
                    showPassword ? "Hide password" : "Show password"
                  }
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <div className="auth-form-options">
              <label className="auth-checkbox">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(event) => setRememberMe(event.target.checked)}
                />

                <span>Remember me</span>
              </label>

              <button type="button" className="auth-link-button">
                Forgot password?
              </button>
            </div>

            {error && <div className="auth-error">{error}</div>}

            <button
              type="submit"
              className="auth-primary-button"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Signing in..." : "Sign in"}
            </button>

            <div className="auth-divider">
              <span>or continue with</span>
            </div>

            <button type="button" className="auth-google-button">
              <span className="google-letter">G</span>
              Continue with Google
            </button>
          </form>

          <p className="auth-switch">
            Don&apos;t have an account?{" "}
            <button type="button" onClick={() => navigate("/register")}>
              Sign up
            </button>
          </p>
        </div>
      </section>
    </div>
  );
}

export default LoginPage;