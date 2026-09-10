import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BrainCircuit,
  Eye,
  EyeOff,
  GraduationCap,
  Users,
} from "lucide-react";

import { useAuth } from "../../contexts/AuthContext.jsx";

function RegisterPage() {
  const navigate = useNavigate();
  const { register } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] =
    useState(false);

  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    setError("");

    if (
      !fullName.trim() ||
      !email.trim() ||
      !password ||
      !confirmPassword
    ) {
      setError("Please complete all fields.");
      return;
    }

    if (password.length < 8) {
      setError(
        "Password must be at least 8 characters long.",
      );
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      setIsSubmitting(true);

      await register({
        fullName: fullName.trim(),
        email: email.trim(),
        password,
      });

      navigate("/login", {
        replace: true,
      });
    } catch (err) {
      if (err.code === "EMAIL_ALREADY_EXISTS") {
        setError(
          "An account with this email already exists.",
        );
      } else if (err.code === "VALIDATION_ERROR") {
        setError(
          "Please check your details and try again.",
        );
      } else {
        setError(
          "Unable to create account. Please try again.",
        );
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
              <GraduationCap size={24} />
            </div>

            <div>
              <strong>Smart Peer</strong>
              <span>Companion</span>
            </div>
          </div>

          <div className="auth-hero-main">
            <h1>
              Study smarter,
              <br />
              together.
            </h1>

            <p>
              Your intelligent learning companion that
              transforms lecture notes into interactive
              study experiences.
            </p>

            <div className="auth-feature-list">
              <div className="auth-feature">
                <div className="auth-feature-icon">
                  <BrainCircuit size={20} />
                </div>

                <div>
                  <strong>AI Study Assistant</strong>
                  <span>
                    Ask questions and understand difficult
                    concepts faster.
                  </span>
                </div>
              </div>

              <div className="auth-feature">
                <div className="auth-feature-icon">
                  <Users size={20} />
                </div>

                <div>
                  <strong>
                    Collaborative Study Groups
                  </strong>
                  <span>
                    Learn together and share knowledge with
                    classmates.
                  </span>
                </div>
              </div>

              <div className="auth-feature">
                <div className="auth-feature-icon">
                  <BrainCircuit size={20} />
                </div>

                <div>
                  <strong>Knowledge Graphs</strong>
                  <span>
                    Turn your notes into connected concepts
                    and learning paths.
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="auth-testimonial">
            <p>
              “SPC completely changed the way I prepare for
              exams. Everything I need is finally in one
              place.”
            </p>

            <span>— University Student</span>
          </div>
        </div>
      </section>

      <section className="auth-form-section">
        <div className="auth-form-container">
          <h2>Create account</h2>

          <p className="auth-form-subtitle">
            Join Smart Peer Companion and start studying
            smarter.
          </p>

          <form
            className="auth-form"
            onSubmit={handleSubmit}
          >
            <div className="auth-field">
              <label htmlFor="full-name">
                Full Name
              </label>

              <input
                id="full-name"
                type="text"
                placeholder="Enter your full name"
                value={fullName}
                onChange={(event) =>
                  setFullName(event.target.value)
                }
                disabled={isSubmitting}
              />
            </div>

            <div className="auth-field">
              <label htmlFor="register-email">
                University Email
              </label>

              <input
                id="register-email"
                type="email"
                placeholder="Enter your university email"
                value={email}
                onChange={(event) =>
                  setEmail(event.target.value)
                }
                disabled={isSubmitting}
              />
            </div>

            <div className="auth-field">
              <label htmlFor="register-password">
                Password
              </label>

              <div className="auth-password-wrapper">
                <input
                  id="register-password"
                  type={
                    showPassword
                      ? "text"
                      : "password"
                  }
                  placeholder="Create a password"
                  value={password}
                  onChange={(event) =>
                    setPassword(event.target.value)
                  }
                  disabled={isSubmitting}
                />

                <button
                  type="button"
                  className="auth-password-toggle"
                  onClick={() =>
                    setShowPassword(
                      (current) => !current,
                    )
                  }
                  aria-label={
                    showPassword
                      ? "Hide password"
                      : "Show password"
                  }
                >
                  {showPassword ? (
                    <EyeOff size={18} />
                  ) : (
                    <Eye size={18} />
                  )}
                </button>
              </div>
            </div>

            <div className="auth-field">
              <label htmlFor="confirm-password">
                Confirm Password
              </label>

              <div className="auth-password-wrapper">
                <input
                  id="confirm-password"
                  type={
                    showConfirmPassword
                      ? "text"
                      : "password"
                  }
                  placeholder="Confirm your password"
                  value={confirmPassword}
                  onChange={(event) =>
                    setConfirmPassword(
                      event.target.value,
                    )
                  }
                  disabled={isSubmitting}
                />

                <button
                  type="button"
                  className="auth-password-toggle"
                  onClick={() =>
                    setShowConfirmPassword(
                      (current) => !current,
                    )
                  }
                  aria-label={
                    showConfirmPassword
                      ? "Hide password"
                      : "Show password"
                  }
                >
                  {showConfirmPassword ? (
                    <EyeOff size={18} />
                  ) : (
                    <Eye size={18} />
                  )}
                </button>
              </div>
            </div>

            {error && (
              <div className="auth-error">
                {error}
              </div>
            )}

            <button
              type="submit"
              className="auth-submit-button"
              disabled={isSubmitting}
            >
              {isSubmitting
                ? "Creating account..."
                : "Create Account"}
            </button>
          </form>

          <p className="auth-signup-text">
            Already have an account?{" "}
            <button
              type="button"
              className="auth-inline-link"
              onClick={() => navigate("/login")}
            >
              Sign in
            </button>
          </p>
        </div>
      </section>
    </div>
  );
}

export default RegisterPage;