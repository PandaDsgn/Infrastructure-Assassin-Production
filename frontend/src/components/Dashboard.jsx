import React, { useState, useEffect } from "react";
import ResourceCard from "./ResourceCard";
import { getAuth, API_BASE_URL } from "../firebase";
import AdminPanel from "./AdminPanel";

export default function Dashboard({
  userRole,
  userName,
  onLogout,
  toggleChat,
  openInbox,
}) {
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [theme, setTheme] = useState(localStorage.getItem("theme") || "light");

  const fetchAuditData = async () => {
    try {
      const token = sessionStorage.getItem("aegis_token");
      const res = await fetch(`${API_BASE_URL}/api/audit?t=${Date.now()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setResources(data);
    } catch (err) {
      console.error("Failed to fetch audit data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditData();
    const interval = setInterval(fetchAuditData, 15000);
    return () => clearInterval(interval);
  }, []);

  const executeSecurityAction = async (actionType, resourceId) => {
    try {
      const token = sessionStorage.getItem("aegis_token");
      const res = await fetch(`${API_BASE_URL}/api/action`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ actionType, resource_id: resourceId }),
      });
      const data = await res.json();
      if (data.pending) alert(`🛡️ DISPATCHED: ${data.message}`);
      else alert(`✅ SUCCESS: ${data.message}`);
      fetchAuditData(); // Refresh immediately after action
    } catch (err) {
      alert("Action failed.");
    }
  };

  const toggleTheme = () => {
    const newTheme = theme === "light" ? "dark" : "light";
    setTheme(newTheme);
    localStorage.setItem("theme", newTheme);
    if (newTheme === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  };

  // Analytics Calculations
  const totalCost = resources.reduce((acc, curr) => {
    if (curr.status === "Active" || curr.status === "Pending Approval") {
      return acc + (Number(curr.monthly_cost) || 0);
    }
    return acc;
  }, 0);

  const savedCost = resources.reduce((acc, curr) => {
    const action = String(curr.recommended_action).toUpperCase();
    if (
      (curr.status === "Active" || curr.status === "Pending Approval") &&
      (action.includes("TERMINATE") || action.includes("QUARANTINE"))
    ) {
      return acc + (Number(curr.monthly_cost) || 0);
    }
    return acc;
  }, 0);

  const percentReduction =
    totalCost > 0 ? ((savedCost / totalCost) * 100).toFixed(1) : "0.0";

  return (
    <div id="main-app" style={{ display: "block" }}>
      <button className="agent-open-btn" onClick={toggleChat}>
        <img
          src="https://res.cloudinary.com/dpwmdsj4r/image/upload/v1783199749/chat_jajw0v.png"
          alt="Chat"
          className="theme-invert-icon"
          style={{ height: "20px", width: "20px" }}
        />{" "}
        Agent
      </button>

      <header>
        <div>
          <h1>Infrastructure Assassin</h1>
          <p style={{ color: "var(--text-muted)", margin: 0 }}>
            Automated IT Cost & Security Optimization
          </p>
        </div>
        <div className="user-profile">
          <div className="inbox-launchers">
            {userRole === "IT-Director" && (
              <button
                className="icon-btn"
                onClick={() => openInbox("incoming")}
              >
                <img
                  src="https://res.cloudinary.com/dpwmdsj4r/image/upload/v1783199749/incoming_tqlyek.png"
                  alt="Incoming"
                  className="theme-invert-icon"
                  style={{ height: "18px", width: "18px" }}
                />
                <span className="badge-dot" id="incoming-inbox-badge"></span>
              </button>
            )}
            {userRole !== "IT-Director" && (
              <button
                className="icon-btn"
                onClick={() => openInbox("outgoing")}
              >
                <img
                  src="https://res.cloudinary.com/dpwmdsj4r/image/upload/v1783199749/outgoing_l7xtol.png"
                  alt="Outgoing"
                  className="theme-invert-icon"
                  style={{ height: "18px", width: "18px" }}
                />
                <span
                  className="badge-dot neutral"
                  id="outgoing-inbox-badge"
                ></span>
              </button>
            )}
          </div>
          <button className="theme-toggle" onClick={toggleTheme}>
            Evening Mode
          </button>
          <div className="user-role">{userRole}</div>
          <div className="user-name">{userName}</div>
          <button className="btn-logout" onClick={onLogout}>
            Sign Out
          </button>
        </div>
      </header>

      <div className="analytics-bar">
        <div className="stat-box">
          <div className="label">Total Monitored Spend</div>
          <div className="value">₹{totalCost.toLocaleString("en-IN")}</div>
        </div>
        <div className="stat-box">
          <div className="label">Identified Waste & Risk</div>
          <div className="value val-green">
            ₹{savedCost.toLocaleString("en-IN")}
          </div>
        </div>
        <div className="stat-box">
          <div className="label">Projected Reduction</div>
          <div className="value val-green">{percentReduction}%</div>
        </div>
      </div>

      {loading ? (
        <div id="loadingText" style={{ display: "flex" }}>
          Analyzing infrastructure telemetry via cloud AI...
        </div>
      ) : (
        <div className="dashboard">
          {resources.map((item) => (
            <ResourceCard
              key={item.id}
              item={item}
              onExecuteAction={executeSecurityAction}
            />
          ))}
        </div>
      )}
    </div>
  );
}
