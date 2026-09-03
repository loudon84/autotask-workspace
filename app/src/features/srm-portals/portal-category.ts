import { FileSpreadsheet, ShoppingCart, Workflow } from "lucide-react";
import type { NavItem } from "@/components/layout/types";

export const PORTAL_CATEGORY = {
  TIANDI: "TIANDI",
  BOE: "BOE",
} as const;

export type PortalCategory =
  (typeof PORTAL_CATEGORY)[keyof typeof PORTAL_CATEGORY];

export const DEFAULT_PORTAL_CATEGORY = PORTAL_CATEGORY.TIANDI;

export const PORTAL_CATEGORY_OPTIONS: ReadonlyArray<{
  value: PortalCategory;
  label: string;
}> = [
  { value: PORTAL_CATEGORY.TIANDI, label: "天地伟业" },
  { value: PORTAL_CATEGORY.BOE, label: "京东方" },
];

type ProcessMenuItem = {
  title: string;
  url: "/processes" | "/process-instances/statements";
  icon: typeof ShoppingCart;
};

const PROCESS_MENU_BY_CATEGORY: Record<PortalCategory, ProcessMenuItem[]> = {
  TIANDI: [
    { title: "客户订单", url: "/processes", icon: ShoppingCart },
    {
      title: "对账单",
      url: "/process-instances/statements",
      icon: FileSpreadsheet,
    },
  ],
  BOE: [],
};

export function portalCategoryLabel(code: string | undefined): string {
  const match = PORTAL_CATEGORY_OPTIONS.find((item) => item.value === code);
  const trimmed = code?.trim();
  if (match?.label) {
    return match.label;
  }
  return trimmed || "—";
}

export function isTiandiCategory(code: string | undefined): boolean {
  return (code || DEFAULT_PORTAL_CATEGORY) === PORTAL_CATEGORY.TIANDI;
}

export function processInstanceNavItem(): NavItem {
  return {
    title: "流程实例",
    icon: Workflow,
    items: PORTAL_CATEGORY_OPTIONS.filter(
      (option) => PROCESS_MENU_BY_CATEGORY[option.value].length > 0
    ).map((option) => ({
      title: option.label,
      items: PROCESS_MENU_BY_CATEGORY[option.value].map((item) => ({
        title: item.title,
        url: item.url,
        icon: item.icon,
      })),
    })),
  };
}
