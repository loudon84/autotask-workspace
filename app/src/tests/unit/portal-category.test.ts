import { describe, expect, it } from "vitest";
import {
  DEFAULT_PORTAL_CATEGORY,
  isTiandiCategory,
  portalCategoryLabel,
  PORTAL_CATEGORY,
  PORTAL_CATEGORY_OPTIONS,
  processInstanceNavItem,
} from "@/features/srm-portals/portal-category";

describe("portal-category registry", () => {
  it("maps codes to display names", () => {
    expect(portalCategoryLabel(PORTAL_CATEGORY.TIANDI)).toBe("天地伟业");
    expect(portalCategoryLabel(PORTAL_CATEGORY.BOE)).toBe("京东方");
  });

  it("treats missing category as 天地伟业", () => {
    expect(isTiandiCategory(undefined)).toBe(true);
    expect(isTiandiCategory(DEFAULT_PORTAL_CATEGORY)).toBe(true);
    expect(isTiandiCategory(PORTAL_CATEGORY.BOE)).toBe(false);
  });

  it("builds 流程实例 → 天地伟业 menu without 京东方", () => {
    const nav = processInstanceNavItem();
    expect(nav.title).toBe("流程实例");
    expect("items" in nav && nav.items?.map((item) => item.title)).toEqual([
      "天地伟业",
    ]);
    const tiandi = "items" in nav ? nav.items?.[0] : undefined;
    expect(
      tiandi && "items" in tiandi
        ? tiandi.items?.map((item) => item.title)
        : []
    ).toEqual(["客户订单", "对账单"]);
  });

  it("exposes both categories for shared documents", () => {
    expect(PORTAL_CATEGORY_OPTIONS.map((item) => item.value)).toEqual([
      "TIANDI",
      "BOE",
    ]);
  });
});
