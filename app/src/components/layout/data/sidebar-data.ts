import {
  LayoutDashboard,
  ListTodo,
  GitBranch,
  Boxes,
  Globe,
  Activity,
  FileImage,
  Settings,
  LayoutGrid,
  Monitor,
} from "lucide-react";
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
        { title: "任务列表", url: "/tasks", icon: ListTodo },
        { title: "Web 工作区", url: "/web-workspace", icon: Monitor },
        { title: "任务记录", url: "/artifacts", icon: FileImage },
        {
          title: "管理中心",
          icon: LayoutGrid,
          items: [
            { title: "运行监控", url: "/runs", icon: Activity },
            { title: "客户SRM", url: "/srm-portals", icon: Globe },
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
  "/tasks": "任务列表",
  "/web-workspace": "Web 工作区",
  "/tasks/new": "新建任务",
  "/workflows": "流程模板",
  "/components": "RPA 组件库",
  "/srm-portals": "客户 SRM",
  "/runs": "运行监控",
  "/artifacts": "任务记录",
  "/settings": "系统设置",
};

export function getPageTitle(pathname: string): string {
  if (routeTitles[pathname]) return routeTitles[pathname];
  if (pathname.startsWith("/tasks/")) return "任务详情";
  if (pathname.startsWith("/workflows/")) return "流程模板详情";
  if (pathname.startsWith("/srm-portals/")) return "门户配置";
  if (pathname.startsWith("/runs/")) return "运行详情";
  return "AutoTask Studio";
}
