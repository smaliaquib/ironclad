import { useEffect, useState } from "react";
import App from "./App";
import LoginPage from "./LoginPage";
import RegisterPage from "./RegisterPage";
import { signOutLocal } from "./auth/cognito";
import { AUTH_ENABLED } from "./auth/config";
import { logout, whoami } from "./auth/session";

type View = "loading" | "login" | "register" | "chat";

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
