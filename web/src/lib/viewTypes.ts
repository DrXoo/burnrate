/** Client-side view state for the redesigned workspace (not backend data). */
export type Section = "dashboard" | "transactions" | "review" | "categories" | "rules" | "settings";
export type Theme = "dark" | "light";
export type HeroMode = "dial" | "bar";

export const SECTION_TITLES: Record<Section, string> = {
  dashboard: "Dashboard",
  transactions: "Transactions",
  review: "Review",
  categories: "Categories",
  rules: "Rules & Budgets",
  settings: "Settings",
};
