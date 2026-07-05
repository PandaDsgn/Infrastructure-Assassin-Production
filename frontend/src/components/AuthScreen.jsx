import React, { useState } from "react";
import { getAuth, API_BASE_URL } from "../firebase";

export default function AuthScreen({ onAuthSuccess }) {
  const [isSignUpMode, setIsSignUpMode] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const auth = getAuth();
      let userCredential;

      if (isSignUpMode) {
        userCredential = await auth.createUserWithEmailAndPassword(
          email,
          password,
        );
      } else {
        userCredential = await auth.signInWithEmailAndPassword(email, password);
      }

      const idToken = await userCredential.user.getIdToken();
      sessionStorage.setItem("aegis_token", idToken);

      if (isSignUpMode) {
        await fetch(`${API_BASE_URL}/api/auth/register`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${idToken}`,
          },
          body: JSON.stringify({ name, inviteCode }),
        });
      }

      onAuthSuccess();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div id="sso-screen">
      <div className="auth-card">
        <h2 id="auth-title">
          {isSignUpMode ? "Create Account" : "Welcome Back"}
        </h2>
        <p id="auth-subtitle">Sign in to your ledger</p>

        <form onSubmit={handleAuth}>
          {isSignUpMode && (
            <div className="input-group">
              <label>Full Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="John Doe"
                required
              />
            </div>
          )}

          <div className="input-group">
            <label>Corporate Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              required
            />
          </div>

          <div className="input-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          {isSignUpMode && (
            <div className="input-group">
              <label>Admin Invite Code (Optional)</label>
              <input
                type="password"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
                placeholder="Leave blank for Junior Dev"
              />
            </div>
          )}

          <button type="submit" className="auth-btn" disabled={loading}>
            {loading ? "Processing..." : isSignUpMode ? "Sign Up" : "Sign In"}
          </button>
        </form>

        {error && (
          <p
            className="login-error"
            style={{
              color: "var(--danger)",
              fontSize: "0.85rem",
              textAlign: "center",
              marginTop: "15px",
            }}
          >
            {error}
          </p>
        )}

        <div style={{ textAlign: "center", marginTop: "15px" }}>
          <button
            type="button"
            className="btn-logout"
            onClick={() => setIsSignUpMode(!isSignUpMode)}
          >
            {isSignUpMode
              ? "Already have an account? Sign In"
              : "Don't have an account? Sign Up"}
          </button>
        </div>
      </div>
    </div>
  );
}
