import { useState } from "react";

import {
  useNavigate,
} from "react-router-dom";

import {
  Bot,
  BrainCircuit,
  Eye,
  EyeOff,
  GraduationCap,
  Moon,
  Sun,
  Users,
} from "lucide-react";

import {
  useAuth,
} from "../../contexts/AuthContext.jsx";

import {
  useTheme,
} from "../../contexts/ThemeContext.jsx";

import "../../styles/styles.css";

function RegisterPage() {
  const navigate =
    useNavigate();

  const {
    register,
  } = useAuth();

  const {
    theme,
    toggleTheme,
  } = useTheme();

  const [
    fullName,
    setFullName,
  ] = useState("");

  const [
    email,
    setEmail,
  ] = useState("");

  const [
    password,
    setPassword,
  ] = useState("");

  const [
    confirmPassword,
    setConfirmPassword,
  ] = useState("");

  const [
    showPassword,
    setShowPassword,
  ] = useState(false);

  const [
    showConfirmPassword,
    setShowConfirmPassword,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState("");

  const [
    isSubmitting,
    setIsSubmitting,
  ] = useState(false);

  async function handleSubmit(
    event,
  ) {
    event.preventDefault();

    setError("");

    if (
      !fullName.trim() ||
      !email.trim() ||
      !password ||
      !confirmPassword
    ) {
      setError(
        "Please complete all fields.",
      );

      return;
    }

    if (password.length < 8) {
      setError(
        "Password must be at least 8 characters long.",
      );

      return;
    }

    if (
      password !==
      confirmPassword
    ) {
      setError(
        "Passwords do not match.",
      );

      return;
    }

    try {
      setIsSubmitting(true);

      await register({
        fullName:
          fullName.trim(),

        email:
          email.trim(),

        password,
      });

      navigate(
        "/login",
        {
          replace: true,
        },
      );
    } catch (err) {
      if (
        err.code ===
        "EMAIL_ALREADY_EXISTS"
      ) {
        setError(
          "An account with this email already exists.",
        );
      } else if (
        err.code ===
        "VALIDATION_ERROR"
      ) {
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

      {/* ==================================================
          LEFT HERO
          ================================================== */}

      <section className="auth-hero">

        <div className="auth-hero-content">

          <div className="auth-brand">

            <div className="auth-brand-icon">
              <GraduationCap
                size={28}
              />
            </div>

            <div>
              <strong>
                Smart Peer
              </strong>

              <span>
                Companion
              </span>
            </div>

          </div>

          <div className="auth-hero-copy">

            <h1>
              Study smarter,
              together.
            </h1>

            <p>
              Your intelligent learning
              companion that transforms
              lecture notes into
              interactive study
              experiences.
            </p>

          </div>

          <div className="auth-features">

            <div className="auth-feature">

              <div className="auth-feature-icon">
                <Bot
                  size={21}
                />
              </div>

              <div>
                <strong>
                  AI Study Assistant
                </strong>

                <span>
                  Ask questions and
                  understand difficult
                  concepts faster.
                </span>
              </div>

            </div>

            <div className="auth-feature">

              <div className="auth-feature-icon">
                <Users
                  size={21}
                />
              </div>

              <div>
                <strong>
                  Collaborative Study
                  Groups
                </strong>

                <span>
                  Learn together and
                  share knowledge with
                  classmates.
                </span>
              </div>

            </div>

            <div className="auth-feature">

              <div className="auth-feature-icon">
                <BrainCircuit
                  size={21}
                />
              </div>

              <div>
                <strong>
                  Knowledge Graphs
                </strong>

                <span>
                  Turn your notes into
                  connected concepts and
                  learning paths.
                </span>
              </div>

            </div>

          </div>

          <div className="auth-quote">

            <p>
              “SPC completely changed
              the way I prepare for
              exams. Everything I need
              is finally in one place.”
            </p>

            <span>
              — University Student
            </span>

          </div>

        </div>

      </section>

      {/* ==================================================
          REGISTER FORM
          ================================================== */}

      <section className="auth-form-section">

        <button
          type="button"
          className="auth-theme-toggle"
          onClick={toggleTheme}
          title={
            theme === "dark"
              ? "Switch to light mode"
              : "Switch to dark mode"
          }
          aria-label={
            theme === "dark"
              ? "Switch to light mode"
              : "Switch to dark mode"
          }
          aria-pressed={
            theme === "dark"
          }
        >
          {theme === "dark" ? (
            <Sun size={19} />
          ) : (
            <Moon size={19} />
          )}
        </button>

        <div className="auth-form-wrapper">

          <div className="auth-mobile-brand">

            <GraduationCap
              size={25}
            />

            <strong>
              Smart Peer Companion
            </strong>

          </div>

          <div className="auth-form-heading">

            <h2>
              Create account
            </h2>

            <p>
              Join Smart Peer
              Companion and start
              studying smarter.
            </p>

          </div>

          <form
            className="auth-form"
            onSubmit={
              handleSubmit
            }
          >

            {/* Full name */}

            <div className="auth-field">

              <label htmlFor="full-name">
                Full Name
              </label>

              <input
                id="full-name"
                type="text"
                placeholder="Enter your full name"
                value={fullName}
                onChange={(
                  event,
                ) =>
                  setFullName(
                    event.target.value,
                  )
                }
                autoComplete="name"
                disabled={
                  isSubmitting
                }
              />

            </div>

            {/* Email */}

            <div className="auth-field">

              <label htmlFor="register-email">
                University Email
              </label>

              <input
                id="register-email"
                type="email"
                placeholder="you@university.edu"
                value={email}
                onChange={(
                  event,
                ) =>
                  setEmail(
                    event.target.value,
                  )
                }
                autoComplete="email"
                disabled={
                  isSubmitting
                }
              />

            </div>

            {/* Password */}

            <div className="auth-field">

              <label htmlFor="register-password">
                Password
              </label>

              <div className="auth-password-field">

                <input
                  id="register-password"
                  type={
                    showPassword
                      ? "text"
                      : "password"
                  }
                  placeholder="Create a password"
                  value={password}
                  onChange={(
                    event,
                  ) =>
                    setPassword(
                      event.target.value,
                    )
                  }
                  autoComplete="new-password"
                  disabled={
                    isSubmitting
                  }
                />

                <button
                  type="button"
                  className="auth-password-toggle"
                  onClick={() =>
                    setShowPassword(
                      (current) =>
                        !current,
                    )
                  }
                  aria-label={
                    showPassword
                      ? "Hide password"
                      : "Show password"
                  }
                >
                  {showPassword ? (
                    <EyeOff
                      size={18}
                    />
                  ) : (
                    <Eye
                      size={18}
                    />
                  )}
                </button>

              </div>

            </div>

            {/* Confirm password */}

            <div className="auth-field">

              <label htmlFor="confirm-password">
                Confirm Password
              </label>

              <div className="auth-password-field">

                <input
                  id="confirm-password"
                  type={
                    showConfirmPassword
                      ? "text"
                      : "password"
                  }
                  placeholder="Confirm your password"
                  value={
                    confirmPassword
                  }
                  onChange={(
                    event,
                  ) =>
                    setConfirmPassword(
                      event.target.value,
                    )
                  }
                  autoComplete="new-password"
                  disabled={
                    isSubmitting
                  }
                />

                <button
                  type="button"
                  className="auth-password-toggle"
                  onClick={() =>
                    setShowConfirmPassword(
                      (current) =>
                        !current,
                    )
                  }
                  aria-label={
                    showConfirmPassword
                      ? "Hide password"
                      : "Show password"
                  }
                >
                  {showConfirmPassword ? (
                    <EyeOff
                      size={18}
                    />
                  ) : (
                    <Eye
                      size={18}
                    />
                  )}
                </button>

              </div>

            </div>

            {/* Error */}

            {error && (
              <div className="auth-error">
                {error}
              </div>
            )}

            {/* Submit */}

            <button
              type="submit"
              className="auth-primary-button"
              disabled={
                isSubmitting
              }
            >
              {isSubmitting
                ? "Creating account..."
                : "Create Account"}
            </button>

          </form>

          <p className="auth-switch">

            Already have an
            account?{" "}

            <button
              type="button"
              onClick={() =>
                navigate(
                  "/login",
                )
              }
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