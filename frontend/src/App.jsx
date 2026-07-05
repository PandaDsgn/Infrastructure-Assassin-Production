import React, { useState, useEffect } from "react";
import { getAuth, initFirebase, API_BASE_URL } from "./firebase";
import AuthScreen from "./components/AuthScreen";
import Dashboard from "./components/Dashboard";
import ChatWidget from "./components/ChatWidget";
import InboxModal from "./components/InboxModal";

export default function App() {
  const [isFirebaseReady, setIsFirebaseReady] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userProfile, setUserProfile] = useState(null);
  const [chatCollapsed, setChatCollapsed] = useState(
    localStorage.getItem("chatCollapsed") === "1",
  );
  const [inboxConfig, setInboxConfig] = useState({ isOpen: false, kind: null });

  // Sync body class for dashboard padding adjustments
  useEffect(() => {
    if (chatCollapsed) {
      document.body.classList.add("chat-collapsed");
    } else {
      document.body.classList.remove("chat-collapsed");
    }
  }, [chatCollapsed]);

  // 1. Initialize Firebase FIRST
  useEffect(() => {
    initFirebase()
      .then(() => setIsFirebaseReady(true))
      .catch((err) => console.error("Firebase init failed:", err));
  }, []);

  // 2. Listen for Auth Changes (Only AFTER Firebase is ready)
  useEffect(() => {
    if (!isFirebaseReady) return;

    const auth = getAuth();
    const unsubscribe = auth.onIdTokenChanged(async (user) => {
      if (!user) {
        sessionStorage.removeItem("aegis_token");
        setIsAuthenticated(false);
        setUserProfile(null);
        return;
      }

      try {
        const token = await user.getIdToken();
        sessionStorage.setItem("aegis_token", token);

        const res = await fetch(`${API_BASE_URL}/api/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        setUserProfile(data);
        setIsAuthenticated(true);
      } catch (err) {
        console.error("Session restore failed", err);
        handleLogout();
      }
    });

    return () => unsubscribe();
  }, [isFirebaseReady]);

  const handleLogout = async () => {
    const token = sessionStorage.getItem("aegis_token");
    if (token) {
      await fetch(`${API_BASE_URL}/api/chat/clear`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    }
    await getAuth().signOut();
  };

  const toggleChat = () => {
    const newState = !chatCollapsed;
    setChatCollapsed(newState);
    localStorage.setItem("chatCollapsed", newState ? "1" : "0");
  };

  // Show a loading screen while fetching backend config
  if (!isFirebaseReady) {
    return (
      <div
        style={{
          display: "flex",
          height: "100vh",
          justifyContent: "center",
          alignItems: "center",
          color: "var(--text-muted)",
        }}
      >
        Initializing Secure Uplink...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthScreen onAuthSuccess={() => setIsAuthenticated(true)} />;
  }

  return (
    <>
      <Dashboard
        userRole={userProfile?.role}
        userName={userProfile?.name}
        onLogout={handleLogout}
        toggleChat={toggleChat}
        openInbox={(kind) => setInboxConfig({ isOpen: true, kind })}
      />

      <ChatWidget collapsed={chatCollapsed} toggleChat={toggleChat} />

      <InboxModal
        isOpen={inboxConfig.isOpen}
        kind={inboxConfig.kind}
        onClose={() => setInboxConfig({ isOpen: false, kind: null })}
        userRole={userProfile?.role}
      />
    </>
  );
}
