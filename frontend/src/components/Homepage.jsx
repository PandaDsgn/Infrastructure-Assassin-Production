import { useEffect, useState } from "react";

export default function Homepage({ onEnter }) {
  const [theme, setTheme] = useState(localStorage.getItem("theme") || "light");

  useEffect(() => {
    if (theme === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }, [theme]);

  const toggleTheme = () => {
    const newTheme = theme === "light" ? "dark" : "light";
    setTheme(newTheme);
    localStorage.setItem("theme", newTheme);
  };

  return (
    <div id="landing-page">
      <div className="landing-topbar">
        <button
          className="icon-btn"
          onClick={toggleTheme}
          aria-label="Toggle theme"
        >
          {theme === "light" ? "🌙" : "☀️"}
        </button>
      </div>

      <div className="landing-hero">
        <h1 className="landing-brand">
          Infrastructure <span className="text-blood-red">Assassin</span>
        </h1>
        <h2 className="landing-title">Audit it. Flag it. Fix it.</h2>
        <p className="landing-sub">
          Continuously monitor your cloud estate, surface waste and threats
          in real time, and dispatch Keep / Update / Quarantine / Terminate
          actions — all with role-based approval built in.
        </p>
        <button className="btn btn-primary landing-cta" onClick={onEnter}>
          Sign In
        </button>
      </div>
    </div>
  );
}
