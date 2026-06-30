import type { PropsWithChildren } from "react";

interface StatusTagProps extends PropsWithChildren {
  tone?: "default" | "good" | "warn" | "danger";
}

export function StatusTag({ tone = "default", children }: StatusTagProps) {
  return <span className={`tag tag-${tone}`}>{children}</span>;
}
