import { useState } from "react";
import Headline from "./Headline";
import RosterBuilder from "./RosterBuilder";
import EngineVsReality from "./EngineVsReality";

const TABS = [
  { id: "headline", label: "הממצא" },
  { id: "reality", label: "מנוע מול מציאות" },
  { id: "builder", label: "בנה קבוצה" },
];

export default function App() {
  const [tab, setTab] = useState("headline");

  return (
    <div dir="rtl" style={{ background: "#0E1420", minHeight: "100vh" }}>
      <style>{NAV}</style>

      <nav className="nav">
        <div className="navin">
          <span className="brand">
            EuroLeague · <b>Roster Optimization</b>
          </span>
          <div className="tabs">
            {TABS.map((t) => (
              <button key={t.id}
                className={"nt" + (tab === t.id ? " on" : "")}
                onClick={() => setTab(t.id)}>
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {tab === "headline" && <Headline onOpenBuilder={() => setTab("builder")} />}
      {tab === "reality" && <EngineVsReality />}
      {tab === "builder" && <RosterBuilder />}
    </div>
  );
}

const NAV = `
@import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;600;700&display=swap');
body{margin:0;background:#0E1420;}
.nav{border-bottom:1px solid #26314A;position:sticky;top:0;z-index:20;
 background:rgba(14,20,32,.94);backdrop-filter:blur(8px);}
.navin{max-width:900px;margin:0 auto;padding:12px clamp(18px,4vw,60px);
 display:flex;justify-content:space-between;align-items:center;gap:16px;
 font-family:'Assistant',system-ui,sans-serif;}
.brand{font-size:12px;letter-spacing:.1em;color:#8894AC;}
.brand b{color:#E9EDF5;font-weight:700;}
.tabs{display:flex;gap:4px;}
.nt{background:none;border:1px solid #26314A;color:#8894AC;border-radius:3px;
 font:inherit;font-size:12.5px;padding:5px 14px;cursor:pointer;}
.nt.on{border-color:#5AA9FF;color:#5AA9FF;}
.nt:hover{color:#E9EDF5;}
`;
