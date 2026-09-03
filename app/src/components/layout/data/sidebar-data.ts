import {
  LayoutDashboard,
  ListTodo,
  GitBranch,
  Boxes,
  Globe,
  FolderOpen,
  Activity,
  FileImage,
  Settings,
  LayoutGrid,
  Monitor,
  Timer,
} from "lucide-react";
import { processInstanceNavItem } from "@/features/srm-portals/portal-category";
import type { SidebarData } from "../types";

export const sidebarData: SidebarData = {
  user: {
    name: "操作员",
    email: "operator@autotask.local",
    avatar: "",
  },
  navGroups: [
    {
      title: "主导航",
      items: [
        { title: "工作台", url: "/dashboard", icon: LayoutDashboard },
        processInstanceNavItem(),
        { title: "任务列表", url: "/tasks", icon: ListTodo },
        { title: "Web 工作区", url: "/web-workspace", icon: Monitor },
        { title: "任务记录", url: "/artifacts", icon: FileImage },
        {
          title: "管理中心",
          icon: LayoutGrid,
          items: [
            { title: "运行监控", url: "/runs", icon: Activity },
            { title: "门户", url: "/srm-portals", icon: Globe },
            { title: "门户分类", url: "/portal-categories", icon: FolderOpen },
            { title: "调度中心", url: "/schedulers", icon: Timer },
            { title: "系统设置", url: "/settings", icon: Settings },
            { title: "流程模板", url: "/workflows", icon: GitBranch },
            { title: "RPA组件库", url: "/components", icon: Boxes },
          ],
        },
      ],
    },
  ],
};

export const routeTitles: Record<string, string> = {
  "/dashboard": "工作台",
  "/processes": "客户订单",
  "/process-instances/statements": "对账单",
  "/process-instances/statements/generate": "生成客户对账单",
  "/tasks": "任务列表",
  "/web-workspace": "Web 工作区",
  "/tasks/new": "新建任务",
  "/workflows": "流程模板",
  "/components": "RPA 组件库",
  "/srm-portals": "客户/供应商门户",
  "/portal-categories": "门户分类",
  "/schedulers": "调度中心",
  "/runs": "运行监控",
  "/artifacts": "任务记录",
  "/settings": "系统设置",
};

export function getPageTitle(pathname: string): string {
  if (routeTitles[pathname]) return routeTitles[pathname];
  if (pathname.startsWith("/processes/") && pathname.endsWith("/dates"))
    return "填写交货日期";
  if (pathname.startsWith("/processes/")) return "客户订单流程实例详情";
  if (pathname.startsWith("/process-instances/statements/")) return "对账单详情";
  if (pathname.startsWith("/tasks/")) return "任务详情";
  if (pathname.startsWith("/workflows/")) return "流程模板详情";
  if (pathname.startsWith("/srm-portals/")) return "门户详情";
  if (pathname.startsWith("/portal-categories/")) return "分类文档";
  if (pathname.startsWith("/schedulers/")) return "调度任务详情";
  if (pathname.startsWith("/runs/")) return "运行详情";
  return "AutoTask Studio";
}
