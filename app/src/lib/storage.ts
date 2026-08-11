const SIDEBAR_KEY = "sidebar_state";

export function getSidebarOpen(): boolean {
  return localStorage.getItem(SIDEBAR_KEY) !== "false";
}

export function setSidebarOpen(open: boolean): void {
  localStorage.setItem(SIDEBAR_KEY, String(open));
}
