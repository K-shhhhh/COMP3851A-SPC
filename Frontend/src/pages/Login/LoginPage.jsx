import "../../styles/styles.css";

function LoginPage({ onRegister }) {
  return (
    <div className="login-page">

      {/* LEFT SIDE */}
      <section className="login-left">
        <div className="brand">
          <div className="brand-icon">🎓</div>
          <div>
            <h3>Smart Peer Companion</h3>
            <p>AI-Powered Learning Platform</p>
          </div>
        </div>

        <div className="hero-content">
          <h1>
            Study smarter,<br />
            together.
          </h1>

          <p className="hero-description">
            Your AI study companion that connects you
            <br />
            with peers, organises notes, and guides your
            <br />
            learning journey.
          </p>

          <div className="features">

            <div className="feature">
              <div className="feature-icon">✧</div>
              <div>
                <strong>@Companion AI</strong>
                <p>ChatMaster, Facilitator & Summarizer modes</p>
              </div>
            </div>

            <div className="feature">
              <div className="feature-icon">♙</div>
              <div>
                <strong>Study Groups</strong>
                <p>Collaborate with peers in real-time</p>
              </div>
            </div>

            <div className="feature">
              <div className="feature-icon">⌘</div>
              <div>
                <strong>Knowledge Graph</strong>
                <p>Visualise how your concepts connect</p>
              </div>
            </div>

          </div>
        </div>

        <div className="testimonial">
          <p>
            "Smart Peer Companion transformed how I study. The AI suggestions
            helped me find partners working on the exact same algorithms problems."
          </p>

          <div className="student">
            <div className="avatar">SC</div>

            <div>
              <strong>Sarah Chen</strong>
              <span>BSc Computer Science, Year 3</span>
            </div>
          </div>
        </div>
      </section>

      {/* RIGHT SIDE */}
      <section className="login-right">

        <div className="login-form">

          <h2>Welcome back</h2>
          <p className="subtitle">Sign in to your student account</p>

          <label>University Email</label>

          <input
            type="email"
            placeholder="✉  john@university.edu"
          />

          <label>Password</label>

          <input
            type="password"
            placeholder="🔒  Enter your password"
          />

          <div className="login-options">

            <label className="remember">
              <input type="checkbox" />
              Remember me
            </label>

            <a href="#">Forgot password?</a>

          </div>

          <button className="signin-button">
            Sign in to SPC
          </button>

          <div className="divider">
            <span></span>
            <p>or continue with</p>
            <span></span>
          </div>

          <button className="google-button">
            <strong>G</strong>
            Sign in with Google
          </button>

          <p className="signup">
            No account?{" "}
            <button onClick={onRegister}>
              Sign up free
            </button>
          </p>

        </div>

      </section>

    </div>
  );
}

export default LoginPage;