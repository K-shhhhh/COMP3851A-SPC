// pages/RegisterPage.jsx

function RegisterPage({ onLogin }) {
  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Create Account</h1>
        <p>Join Smart Peer Companion</p>

        <input type="text" placeholder="Full Name" />
        <input type="email" placeholder="Email" />
        <input type="password" placeholder="Password" />
        <input type="password" placeholder="Confirm Password" />

        <button>Create Account</button>

        <p>
          Already have an account?{" "}
          <button className="link-button" onClick={onLogin}>
            Sign In
          </button>
        </p>
      </div>
    </div>
  );
}

export default RegisterPage;