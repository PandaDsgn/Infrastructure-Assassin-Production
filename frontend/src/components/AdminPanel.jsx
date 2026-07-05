import { useState, useEffect } from "react";
import { API_BASE_URL } from "../firebase";

export default function AdminPanel() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchUsers = async () => {
    try {
      const token = sessionStorage.getItem("aegis_token");
      const res = await fetch(`${API_BASE_URL}/api/users?t=${Date.now()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setUsers(data);
    } catch (error) {
      console.error("Failed to fetch users", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleDeleteUser = async (uid) => {
    if (!window.confirm("Are you sure you want to terminate this user?"))
      return;
    try {
      const token = sessionStorage.getItem("aegis_token");
      const res = await fetch(`${API_BASE_URL}/api/users/${uid}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (res.ok) {
        alert("User removed successfully.");
        fetchUsers();
      } else {
        alert(`Operation Fault: ${data.error}`);
      }
    } catch (error) {
      alert("Server error during deletion.");
    }
  };

  return (
    <div id="admin-panel">
      <h3 style={{ marginTop: 0, color: "var(--success)" }}>
        Admin Control Center
      </h3>
      <div>
        <h4 style={{ marginTop: 0 }}>Personnel Directory</h4>
        <div id="user-list-panel">
          {loading ? (
            <p style={{ color: "var(--text-muted)" }}>Loading users...</p>
          ) : users.length === 0 ? (
            <p style={{ color: "var(--text-muted)" }}>
              No other personnel found.
            </p>
          ) : (
            users.map((u) => (
              <div className="inbox-card" key={u.uid}>
                <div>
                  <strong>{u.name}</strong>
                  <br />
                  <span
                    style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}
                  >
                    {u.email} ({u.role})
                  </span>
                </div>
                {u.role === "IT-Director" ? (
                  <span
                    style={{
                      fontSize: "0.85rem",
                      color: "var(--success)",
                      fontWeight: "bold",
                      padding: "8px",
                    }}
                  >
                    ADMIN
                  </span>
                ) : (
                  <button
                    className="btn-reject"
                    onClick={() => handleDeleteUser(u.uid)}
                  >
                    Terminate
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
