import React, { useState, useEffect } from "react";

const SIGNAL_TYPES = [
  { key: "keep", label: "K", full: "Keep" },
  { key: "update", label: "U", full: "Update" },
  { key: "quarantine", label: "Q", full: "Quarantine" },
  { key: "terminate", label: "T", full: "Terminate" },
];

const normalizeAction = (action) => {
  const a = String(action || "").toUpperCase();
  if (a.includes("TERMINATE")) return "terminate";
  if (a.includes("QUARANTINE")) return "quarantine";
  if (a.includes("UPDATE")) return "update";
  return "keep";
};

export default function ResourceCard({ item, onExecuteAction }) {
  const [pendingAction, setPendingAction] = useState(null);
  const [timeLeft, setTimeLeft] = useState(0);

  const cost = Number(item.monthly_cost) || 0;

  const isAwaitingApproval = item.status === "Pending Approval";
  const targetAction = normalizeAction(
    isAwaitingApproval
      ? item.pending_action_type || item.recommended_action
      : item.recommended_action,
  );

  const signalDotClasses = (key) => {
    const classes = ["signal-dot", `dot-${key}`];
    if (!isAwaitingApproval && targetAction === key) classes.push("active");
    if (isAwaitingApproval && targetAction === key)
      classes.push("pending-target");
    return classes.join(" ");
  };

  useEffect(() => {
    let timer;
    if (timeLeft > 0) {
      timer = setInterval(() => setTimeLeft((prev) => prev - 1), 1000);
    } else if (timeLeft === 0 && pendingAction) {
      onExecuteAction(pendingAction, item.id);
      setPendingAction(null);
    }
    return () => clearInterval(timer);
  }, [timeLeft, pendingAction, item.id, onExecuteAction]);

  const initiateLifecycle = (actionType) => {
    setPendingAction(actionType);
    setTimeLeft(86400); // 24 hours in seconds
  };

  const cancelLifecycle = () => {
    setPendingAction(null);
    setTimeLeft(0);
    alert("Action execution halted successfully before sending.");
  };

  const executeNow = () => {
    onExecuteAction(pendingAction, item.id);
    setPendingAction(null);
    setTimeLeft(0);
  };

  const formatTime = (seconds) => {
    if (seconds >= 3600) return Math.ceil(seconds / 3600) + "h";
    if (seconds >= 60) return Math.ceil(seconds / 60) + "m";
    return seconds + "s";
  };

  return (
    <div className="card">
      <div>
        <div className="status-signal">
          {SIGNAL_TYPES.map(({ key, label, full }) => (
            <div
              key={key}
              className={signalDotClasses(key)}
              title={
                isAwaitingApproval && targetAction === key
                  ? `Pending approval: ${full}`
                  : full
              }
            >
              <span className="dot"></span>
              <span className="label">{label}</span>
            </div>
          ))}
          {isAwaitingApproval && (
            <span className="status-signal-caption">Awaiting approval</span>
          )}
        </div>

        <div className="card-header">
          <div>
            <h3 className="resource-name">{item.resource_name}</h3>
            <div className="resource-type">{item.resource_type}</div>
          </div>
        </div>

        <div className="details">
          <div>
            Owner: <br />
            <strong>{item.employee_name}</strong>
          </div>
          <div>
            Installed: <br />
            <strong>{item.install_date}</strong>
          </div>
          <div>
            Monthly Cost: <br />
            <strong>₹{cost.toLocaleString("en-IN")}</strong>
          </div>
          <div>
            Time Idle: <br />
            <strong>{item.days_since_last_login} days</strong>
          </div>
        </div>
      </div>

      <div className="action-bar">
        {pendingAction ? (
          <>
            <button className="btn-undo-active" onClick={cancelLifecycle}>
              ⏳ Undo ({formatTime(timeLeft)})
            </button>
            <button className="btn-now-active" onClick={executeNow}>
              {pendingAction} Now
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => initiateLifecycle("KEEP")}
              disabled={item.status === "Pending Approval"}
            >
              Keep
            </button>
            <button
              onClick={() => initiateLifecycle("UPDATE")}
              disabled={item.status === "Pending Approval"}
            >
              Update
            </button>
            <button
              onClick={() => initiateLifecycle("QUARANTINE")}
              disabled={item.status === "Pending Approval"}
            >
              Quarantine
            </button>
            <button
              className="btn-terminate"
              onClick={() => initiateLifecycle("TERMINATE")}
              disabled={item.status === "Pending Approval"}
            >
              Terminate
            </button>
          </>
        )}
      </div>
    </div>
  );
}
