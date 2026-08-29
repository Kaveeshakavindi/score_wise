import { useState } from "react";
import { clearTokens, isLoggedIn } from "./api";
import { DocumentsView } from "./components/DocumentsView";
import { LoginView } from "./components/LoginView";

export function App() {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn());

  function handleLogout() {
    clearTokens();
    setLoggedIn(false);
  }

  if (!loggedIn) {
    return <LoginView onLoggedIn={() => setLoggedIn(true)} />;
  }

  return (
    <>
      <header className="topbar">
        <span>ScoreWise Admin</span>
        <button type="button" className="link" onClick={handleLogout}>
          Log out
        </button>
      </header>
      <DocumentsView onSessionExpired={handleLogout} />
    </>
  );
}
