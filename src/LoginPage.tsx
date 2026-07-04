import { useState } from "react";
import { signIn } from "./auth/cognito";
import { establishSession } from "./auth/session";
import "./AuthPages.css";

interface LoginPageProps {
  onAuthenticated: () => void;
  onNavigateRegister: () => void;
}

function LoginPage({ onAuthenticated, onNavigateRegister }: LoginPageProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const tokens = await signIn(email.trim(), password);
      await establishSession(tokens);
      onAuthenticated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "sign-in failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          Ironclad
        </div>
        <h1>Sign in</h1>

        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </label>

        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>

        {error && <div className="auth-error">{error}</div>}

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Signing in..." : "Sign in"}
        </button>

        <div className="auth-switch">
          Don't have an account?{" "}
          <button type="button" className="link-btn" onClick={onNavigateRegister}>
            Create one
          </button>
        </div>
      </form>
    </div>
  );
}

export default LoginPage;
