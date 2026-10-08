import { MonthSelector } from "./MonthSelector";
import { IconLogout, IconMenu, IconMoon } from "./icons";
import type { HeroMode, Section, Theme } from "../lib/viewTypes";
import { SECTION_TITLES } from "../lib/viewTypes";

interface TopBarProps {
  section: Section;
  month: string;
  monthLabel: string;
  onSelectMonth: (month: string) => void;
  theme: Theme;
  heroMode: HeroMode;
  onToggleTheme: () => void;
  onSetHeroMode: (mode: HeroMode) => void;
  onToggleMenu: () => void;
  onLogout: () => void;
}

export function TopBar({
  section,
  month,
  monthLabel,
  onSelectMonth,
  theme,
  heroMode,
  onToggleTheme,
  onSetHeroMode,
  onToggleMenu,
  onLogout,
}: TopBarProps) {
  // A month means nothing on Settings, so neither the label nor the selector appears
  // there: a control would imply the page responds to it.
  const monthScoped = section !== "settings";

  return (
    <div
      className="br-topbar"
      style={{
        position: "sticky",
        top: 0,
        zIndex: 20,
        background: "color-mix(in oklab, var(--bg) 86%, transparent)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid var(--line)",
        padding: "14px 30px",
        display: "flex",
        alignItems: "center",
        gap: 16,
      }}
    >
      <button
        type="button"
        className="br-hamburger"
        aria-label="Open menu"
        onClick={onToggleMenu}
        style={{
          flex: "none",
          width: 34,
          height: 34,
          borderRadius: 9,
          border: "1px solid var(--line)",
          background: "var(--bg-3)",
          color: "var(--text-2)",
          cursor: "pointer",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <IconMenu />
      </button>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="num" style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em" }}>
          {SECTION_TITLES[section]}
        </div>
        {monthScoped ? (
          // The label is the way back to the current month, which keeps that one action
          // away from any month the owner has reached. "" is what asks for it, so the
          // month comes from the backend rather than from a clock here.
          <button
            type="button"
            title="Back to the current month"
            onClick={() => onSelectMonth("")}
            style={{
              border: "none",
              background: "none",
              padding: 0,
              font: "500 12.5px 'Hanken Grotesque', sans-serif",
              color: "var(--text-3)",
              cursor: "pointer",
              textAlign: "left",
            }}
          >
            {monthLabel}
          </button>
        ) : null}
      </div>

      {monthScoped ? <MonthSelector month={month} onSelectMonth={onSelectMonth} /> : null}

      {section === "dashboard" ? (
        <div
          style={{
            display: "flex",
            background: "var(--bg-3)",
            border: "1px solid var(--line)",
            borderRadius: 9,
            padding: 3,
            gap: 2,
          }}
        >
          {(["dial", "bar"] as HeroMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => onSetHeroMode(mode)}
              style={{
                border: "none",
                cursor: "pointer",
                padding: "5px 10px",
                borderRadius: 6,
                font: "500 12px 'Hanken Grotesque', sans-serif",
                background: heroMode === mode ? "var(--accent)" : "transparent",
                color: heroMode === mode ? "#0a0d10" : "var(--text-2)",
                textTransform: "capitalize",
              }}
            >
              {mode}
            </button>
          ))}
        </div>
      ) : null}

      <button
        type="button"
        title="Toggle theme"
        aria-label="Toggle theme"
        onClick={onToggleTheme}
        style={{
          flex: "none",
          width: 34,
          height: 34,
          borderRadius: 9,
          border: "1px solid var(--line)",
          background: "var(--bg-3)",
          color: "var(--text-2)",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <IconMoon color={theme === "light" ? "var(--accent)" : "currentColor"} />
      </button>

      <button
        type="button"
        title="Sign out"
        aria-label="Sign out"
        onClick={onLogout}
        style={{
          flex: "none",
          width: 34,
          height: 34,
          borderRadius: 9,
          border: "1px solid var(--line)",
          background: "var(--bg-3)",
          color: "var(--text-2)",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <IconLogout />
      </button>
    </div>
  );
}
