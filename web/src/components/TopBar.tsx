import { IconMenu, IconMoon } from "./icons";
import type { HeroMode, Section, Theme } from "../lib/viewTypes";
import { SECTION_TITLES } from "../lib/viewTypes";

interface TopBarProps {
  section: Section;
  monthLabel: string;
  theme: Theme;
  heroMode: HeroMode;
  onToggleTheme: () => void;
  onSetHeroMode: (mode: HeroMode) => void;
  onToggleMenu: () => void;
}

export function TopBar({ section, monthLabel, theme, heroMode, onToggleTheme, onSetHeroMode, onToggleMenu }: TopBarProps) {
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
        <div style={{ fontSize: 12.5, color: "var(--text-3)" }}>{monthLabel}</div>
      </div>

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
    </div>
  );
}
