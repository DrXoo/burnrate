import type { CSSProperties, ReactNode } from "react";

import {
  IconCategories,
  IconDashboard,
  IconReview,
  IconRules,
  IconSettings,
  IconTransactions,
  LogoMark,
} from "./icons";
import type { Section } from "../lib/viewTypes";

interface SidebarProps {
  section: Section;
  reviewCount: number;
  isOpen: boolean;
  onNavigate: (section: Section) => void;
}

const navButtonStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 11,
  padding: "9px 11px",
  border: "none",
  borderRadius: 9,
  cursor: "pointer",
  font: "500 13.5px 'Hanken Grotesque', sans-serif",
  textAlign: "left",
};

function NavItem({
  active,
  label,
  icon,
  badge,
  onClick,
}: {
  active: boolean;
  label: string;
  icon: ReactNode;
  badge?: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        ...navButtonStyle,
        background: active ? "var(--nav-active)" : "transparent",
        color: active ? "var(--text)" : "var(--text-2)",
      }}
    >
      {icon}
      <span style={{ flex: 1 }}>{label}</span>
      {badge}
    </button>
  );
}

export function Sidebar({ section, reviewCount, isOpen, onNavigate }: SidebarProps) {
  return (
    <aside
      className={`br-sidebar ${isOpen ? "br-sidebar-open" : ""}`.trim()}
      style={{
        flex: "none",
        width: 236,
        background: "var(--bg-2)",
        borderRight: "1px solid var(--line)",
        display: "flex",
        flexDirection: "column",
        position: "sticky",
        top: 0,
        height: "100vh",
      }}
    >
      <div style={{ padding: "22px 20px 16px", display: "flex", alignItems: "center", gap: 9 }}>
        <div
          style={{
            width: 26,
            height: 26,
            borderRadius: 7,
            background: "var(--accent)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <LogoMark />
        </div>
        <span style={{ fontWeight: 700, fontSize: 15.5, letterSpacing: "-0.02em" }}>BurnRate</span>
      </div>

      <nav style={{ padding: "8px 12px", display: "flex", flexDirection: "column", gap: 2 }}>
        <NavItem
          active={section === "dashboard"}
          label="Dashboard"
          icon={<IconDashboard />}
          onClick={() => onNavigate("dashboard")}
        />
        <NavItem
          active={section === "transactions"}
          label="Transactions"
          icon={<IconTransactions />}
          onClick={() => onNavigate("transactions")}
        />
        <NavItem
          active={section === "review"}
          label="Review"
          icon={<IconReview />}
          badge={
            reviewCount > 0 ? (
              <span
                className="num"
                style={{
                  background: "var(--over)",
                  color: "#0a0d10",
                  fontSize: 11,
                  fontWeight: 700,
                  minWidth: 18,
                  height: 18,
                  padding: "0 5px",
                  borderRadius: 9,
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {reviewCount}
              </span>
            ) : undefined
          }
          onClick={() => onNavigate("review")}
        />
        <NavItem
          active={section === "categories"}
          label="Categories"
          icon={<IconCategories />}
          onClick={() => onNavigate("categories")}
        />
        <NavItem
          active={section === "rules"}
          label="Rules & Budgets"
          icon={<IconRules />}
          onClick={() => onNavigate("rules")}
        />
        <NavItem
          active={section === "settings"}
          label="Settings"
          icon={<IconSettings />}
          onClick={() => onNavigate("settings")}
        />
      </nav>

      <div style={{ marginTop: "auto", padding: "14px 16px", borderTop: "1px solid var(--line)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "6px 4px" }}>
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: "50%",
              background: "var(--bg-4)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 12,
              fontWeight: 700,
              color: "var(--text-2)",
            }}
          >
            M
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: 12.5,
                fontWeight: 600,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              My finances
            </div>
            <div style={{ fontSize: 11, color: "var(--text-3)" }}>Self-hosted · EUR</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
