import type { CSSProperties, ReactNode } from "react";

interface IconProps {
  size?: number;
  /** Stroke color; defaults to the current text color. */
  color?: string;
  style?: CSSProperties;
}

interface SvgProps extends IconProps {
  width: number;
  children: ReactNode;
  strokeWidth?: number;
  fill?: string;
}

function Svg({ size, color = "currentColor", width, strokeWidth = 1.7, fill = "none", style, children }: SvgProps) {
  const dimension = size ?? width;
  return (
    <svg
      width={dimension}
      height={dimension}
      viewBox="0 0 24 24"
      fill={fill}
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={style}
    >
      {children}
    </svg>
  );
}

/** BurnRate gauge mark, used inside the accent square. */
export function LogoMark({ size = 15, color = "#0a0d10" }: IconProps) {
  return (
    <Svg width={size} size={size} color={color} strokeWidth={2.4}>
      <path d="M4 15a8 8 0 0 1 16 0" />
      <path d="M12 15l4-4" />
    </Svg>
  );
}

export function IconDashboard(props: IconProps) {
  return (
    <Svg width={17} {...props}>
      <path d="M4 16a8 8 0 0 1 16 0" />
      <path d="M12 16l3.5-4" />
      <circle cx="12" cy="16" r="1.3" fill="currentColor" stroke="none" />
    </Svg>
  );
}

export function IconTransactions(props: IconProps) {
  return (
    <Svg width={17} {...props}>
      <path d="M8 7h11" />
      <path d="M8 12h11" />
      <path d="M8 17h11" />
      <circle cx="4.5" cy="7" r="1" />
      <circle cx="4.5" cy="12" r="1" />
      <circle cx="4.5" cy="17" r="1" />
    </Svg>
  );
}

export function IconReview(props: IconProps) {
  return (
    <Svg width={17} {...props}>
      <path d="M4 13l2.5-7A2 2 0 0 1 8.4 4.7h7.2a2 2 0 0 1 1.9 1.3L20 13" />
      <path d="M4 13h4a2 2 0 0 1 4 0h0a2 2 0 0 1 4 0h4" />
      <path d="M4 13v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" />
    </Svg>
  );
}

export function IconCategories(props: IconProps) {
  return (
    <Svg width={17} {...props}>
      <rect x="4" y="4" width="7" height="7" rx="1.5" />
      <rect x="13" y="4" width="7" height="7" rx="1.5" />
      <rect x="4" y="13" width="7" height="7" rx="1.5" />
      <rect x="13" y="13" width="7" height="7" rx="1.5" />
    </Svg>
  );
}

export function IconRules(props: IconProps) {
  return (
    <Svg width={17} {...props}>
      <path d="M5 8h14" />
      <circle cx="9" cy="8" r="2.3" fill="var(--bg-2)" />
      <path d="M5 16h14" />
      <circle cx="15" cy="16" r="2.3" fill="var(--bg-2)" />
    </Svg>
  );
}

export function IconSliders(props: IconProps) {
  return (
    <Svg width={13} strokeWidth={1.9} {...props}>
      <path d="M5 8h14" />
      <circle cx="9" cy="8" r="2" />
      <path d="M5 16h14" />
      <circle cx="15" cy="16" r="2" />
    </Svg>
  );
}

export function IconSettings(props: IconProps) {
  return (
    <Svg width={17} {...props}>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 3v2.2M12 18.8V21M21 12h-2.2M5.2 12H3M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6M18.4 18.4l-1.6-1.6M7.2 7.2 5.6 5.6" />
    </Svg>
  );
}

export function IconMoon(props: IconProps) {
  return (
    <Svg width={16} strokeWidth={1.8} {...props}>
      <path d="M20.5 14.5A8.5 8.5 0 1 1 9.5 3.5a6.6 6.6 0 0 0 11 11Z" />
    </Svg>
  );
}

export function IconSync(props: IconProps) {
  return (
    <Svg width={13} strokeWidth={2} {...props}>
      <path d="M20 11A8 8 0 0 0 6.3 5.7L4 8" />
      <path d="M4 4v4h4" />
      <path d="M4 13a8 8 0 0 0 13.7 5.3L20 16" />
      <path d="M20 20v-4h-4" />
    </Svg>
  );
}

export function IconSearch(props: IconProps) {
  return (
    <Svg width={15} strokeWidth={2} {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </Svg>
  );
}

export function IconCheck(props: IconProps) {
  return (
    <Svg width={13} strokeWidth={2.4} {...props}>
      <path d="m5 12 5 5L20 6" />
    </Svg>
  );
}

export function IconPencil(props: IconProps) {
  return (
    <Svg width={14} strokeWidth={1.8} {...props}>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </Svg>
  );
}

export function IconTrash(props: IconProps) {
  return (
    <Svg width={14} strokeWidth={1.8} {...props}>
      <path d="M4 7h16" />
      <path d="M10 11v6M14 11v6" />
      <path d="M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13" />
      <path d="M9 7V4h6v3" />
    </Svg>
  );
}

export function IconLogout(props: IconProps) {
  return (
    <Svg width={17} {...props}>
      <path d="M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3" />
      <path d="M15 12H9" />
      <path d="M13 8l4 4-4 4" />
    </Svg>
  );
}

export function IconMenu(props: IconProps) {
  return (
    <Svg width={18} strokeWidth={1.9} {...props}>
      <path d="M4 7h16" />
      <path d="M4 12h16" />
      <path d="M4 17h16" />
    </Svg>
  );
}

export function IconCard(props: IconProps) {
  return (
    <Svg width={46} strokeWidth={1.5} {...props}>
      <rect x="3" y="6" width="18" height="13" rx="2.5" />
      <path d="M3 10h18" />
      <path d="M7 15h4" />
    </Svg>
  );
}
