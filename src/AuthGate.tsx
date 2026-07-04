import { useEffect, useState } from "react";
import App from "./App";
import LoginPage from "./LoginPage";
import RegisterPage from "./RegisterPage";
import { signOutLocal } from "./auth/cognito";
import { logout, whoami } from "./auth/session";

type View = "loading" | "login" | "register" | "chat";

// Mirrors the infra's enable_auth flag (baked in at build time - see
// Dockerfile/buildspec-cd.yml). While it's off, CloudFront's Lambda@Edge
// isn't attached, so /auth/whoami would just fall through to nginx's SPA
// fallback instead of answering - skip the whole login gate in that case
// rather than misreading that response as "not authenticated".
const AUTH_ENABLED = import.meta.env.VITE_ENABLE_AUTH === "true";

function AuthGate() {
  const [view, setView] = useState<View>(AUTH_ENABLED ? "loading" : "chat");

  useEffect(() => {
    if (!AUTH_ENABLED) return;
    whoami().then((authenticated) => setView(authenticated ? "chat" : "login"));
  }, []);

  const handleSignOut = async () => {
    await logout();
    signOutLocal();
    setView("login");
  };

  switch (view) {
    case "loading":
      return null;
    case "login":
      return (
        <LoginPage
          onAuthenticated={() => setView("chat")}
          onNavigateRegister={() => setView("register")}
        />
      );
    case "register":
      return <RegisterPage onNavigateLogin={() => setView("login")} />;
    case "chat":
      return (
        <App
          onSignOut={AUTH_ENABLED ? handleSignOut : undefined}
          onUnauthorized={() => AUTH_ENABLED && setView("login")}
        />
      );
  }
}

export default AuthGate;
