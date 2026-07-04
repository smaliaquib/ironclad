import { useState } from "react";
import { signUp, confirmSignUp } from "./auth/cognito";
import "./AuthPages.css";

interface RegisterPageProps {
  onNavigateLogin: () => void;
}

function RegisterPage({ onNavigateLogin }: RegisterPageProps) {
  const [step, setStep] = useState<"register" | "confirm" | "done">("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      await signUp(email.trim(), password);
      setStep("confirm");
    } catch (err) {
      setError(err instanceof Error ? err.message : "sign-up failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      await confirmSignUp(email.trim(), code.trim());
      setStep("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "confirmation failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          Ironclad
        </div>

        {step === "register" && (
          <form onSubmit={handleRegister}>
            <h1>Create an account</h1>
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
                autoComplete="new-password"
                minLength={12}
                required
              />
            </label>
            <p className="auth-hint">At least 12 characters, with upper/lowercase, a number, and a symbol.</p>
            {error && <div className="auth-error">{error}</div>}
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Creating account..." : "Create account"}
            </button>
          </form>
        )}

        {step === "confirm" && (
          <form onSubmit={handleConfirm}>
            <h1>Check your email</h1>
            <p className="auth-hint">Enter the confirmation code we sent to {email}.</p>
            <label>
              Confirmation code
              <input
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                autoComplete="one-time-code"
                required
              />
            </label>
            {error && <div className="auth-error">{error}</div>}
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Confirming..." : "Confirm"}
            </button>
          </form>
        )}

        {step === "done" && (
          <>
            <h1>You're all set</h1>
            <p className="auth-hint">Your account is confirmed - sign in to continue.</p>
            <button type="button" onClick={onNavigateLogin}>
              Go to sign in
            </button>
          </>
        )}

        {step !== "done" && (
          <div className="auth-switch">
            Already have an account?{" "}
            <button type="button" className="link-btn" onClick={onNavigateLogin}>
              Sign in
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default RegisterPage;
