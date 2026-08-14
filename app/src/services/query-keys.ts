export const queryKeys = {
  dashboard: {
    all: ["dashboard"] as const,
    summary: () => [...queryKeys.dashboard.all] as const,
  },
  tasks: {
    all: ["tasks"] as const,
    list: (params?: Record<string, unknown>) =>
      params
        ? ([...queryKeys.tasks.all, params] as const)
        : ([...queryKeys.tasks.all] as const),
    detail: (id: string) => [...queryKeys.tasks.all, id] as const,
    auditLogs: (taskId: string) => ["audit-logs", taskId] as const,
    humanAction: (taskId: string) => ["human-action", taskId] as const,
  },
  workflows: {
    all: ["workflows"] as const,
    list: () => [...queryKeys.workflows.all] as const,
    detail: (id: string) => [...queryKeys.workflows.all, id] as const,
  },
  workflowBindings: {
    all: ["workflow-bindings"] as const,
    list: () => [...queryKeys.workflowBindings.all] as const,
  },
  runs: {
    all: ["runs"] as const,
    list: () => [...queryKeys.runs.all] as const,
    detail: (id: string) => [...queryKeys.runs.all, id] as const,
    events: (runId: string) => ["run-events", runId] as const,
    byTask: (taskId: string) => ["runs", "task", taskId] as const,
  },
  portalAccounts: {
    all: ["srm-portals"] as const,
    list: () => [...queryKeys.portalAccounts.all] as const,
    detail: (id: string) => [...queryKeys.portalAccounts.all, id] as const,
  },
  artifacts: {
    all: ["artifacts"] as const,
    list: () => [...queryKeys.artifacts.all] as const,
    byTask: (taskId: string) => ["artifacts", "task", taskId] as const,
    byRun: (runId: string) => ["artifacts", "run", runId] as const,
    downloadUrl: (artifactId: string) =>
      ["artifacts", artifactId, "download-url"] as const,
  },
  workers: {
    all: ["workers"] as const,
    list: () => [...queryKeys.workers.all] as const,
  },
  settings: {
    all: ["settings"] as const,
  },
  rpaComponents: {
    all: ["rpa-components"] as const,
  },
  processInstances: {
    all: ["process-instances"] as const,
    list: (params?: Record<string, unknown>) =>
      params
        ? ([...queryKeys.processInstances.all, params] as const)
        : ([...queryKeys.processInstances.all] as const),
    detail: (id: string) => [...queryKeys.processInstances.all, id] as const,
  },
  search: {
    all: ["search"] as const,
    query: (q: string) => [...queryKeys.search.all, q] as const,
  },
  backendStatus: {
    all: ["backend-status"] as const,
  },
};
