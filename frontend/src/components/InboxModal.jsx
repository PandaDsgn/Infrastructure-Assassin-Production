import { useState, useEffect } from "react";

export default function InboxModal({ isOpen, kind, onClose, userRole }) {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchRequests = async () => {
    setLoading(true);
    try {
      const token = sessionStorage.getItem("aegis_token");
      const endpoint =
        kind === "incoming" ? "/api/approvals" : "/api/requests/outgoing";
      const res = await fetch(`${endpoint}?t=${Date.now()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setRequests(data);
    } catch (error) {
      console.error("Failed to load inbox", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && kind) {
      fetchRequests();
    }
  }, [isOpen, kind]);

  const handleResolve = async (id, decision) => {
    try {
      const token = sessionStorage.getItem("aegis_token");
      const res = await fetch("/api/approvals/resolve", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ id, decision }),
      });
      const data = await res.json();
      alert(data.message);
      fetchRequests();
    } catch (error) {
      alert("Resolution failed.");
    }
  };

  const formatTimestamp = (ts) => {
    if (!ts) return "—";
    return new Date(ts).toLocaleString([], {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay open" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{kind === "incoming" ? "Incoming Inbox" : "Outgoing Inbox"}</h3>
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>
        <div className="modal-body">
          {loading ? (
            <p style={{ color: "var(--text-muted)" }}>Loading...</p>
          ) : requests.length === 0 ? (
            <p style={{ color: "var(--text-muted)" }}>
              No {kind === "incoming" ? "pending" : ""} requests found.
            </p>
          ) : (
            requests.map((req) => (
              <div className="inbox-entry" key={req.id}>
                <div className="inbox-entry-row">
                  {kind === "incoming" ? (
                    <div>
                      <strong>{req.requester}</strong> requests{" "}
                      <strong>{req.action}</strong> authorization for{" "}
                      <em>{req.resource}</em>
                    </div>
                  ) : (
                    <>
                      <div>
                        <strong>{req.action_type}</strong> requested for{" "}
                        <em>{req.resource_name}</em>
                      </div>
                      <span className={`status-tag ${req.status}`}>
                        {req.status}
                      </span>
                    </>
                  )}
                </div>
                <div className="inbox-timestamp">
                  {kind === "incoming"
                    ? formatTimestamp(req.requested_at)
                    : `Sent ${formatTimestamp(req.requested_at)}`}
                </div>
                {kind === "outgoing" && req.resolved_at && (
                  <div className="inbox-timestamp">
                    Resolved {formatTimestamp(req.resolved_at)}{" "}
                    {req.resolved_by && `by ${req.resolved_by}`}
                  </div>
                )}
                {kind === "incoming" && (
                  <div
                    style={{ display: "flex", gap: "10px", marginTop: "10px" }}
                  >
                    <button
                      className="btn-approve"
                      onClick={() => handleResolve(req.id, "Approve")}
                    >
                      Approve
                    </button>
                    <button
                      className="btn-reject"
                      onClick={() => handleResolve(req.id, "Reject")}
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
