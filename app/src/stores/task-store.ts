import { create } from "zustand";
import type {
  AutomationTask,
  AutomationTaskStatus,
} from "@/types/automation-task";

interface TaskStore {
  addedTasks: AutomationTask[];
  overrides: Record<string, Partial<AutomationTask>>;
  addTask: (task: AutomationTask) => void;
  updateTaskStatus: (id: string, status: AutomationTaskStatus) => void;
  updateTask: (id: string, patch: Partial<AutomationTask>) => void;
}

export const useTaskStore = create<TaskStore>((set) => ({
  addedTasks: [],
  overrides: {},
  addTask: (task) =>
    set((state) => ({ addedTasks: [task, ...state.addedTasks] })),
  updateTaskStatus: (id, status) =>
    set((state) => ({
      overrides: {
        ...state.overrides,
        [id]: {
          ...state.overrides[id],
          status,
          updatedAt: new Date().toISOString().replace("T", " ").slice(0, 19),
        },
      },
    })),
  updateTask: (id, patch) =>
    set((state) => ({
      overrides: {
        ...state.overrides,
        [id]: {
          ...state.overrides[id],
          ...patch,
          updatedAt: new Date().toISOString().replace("T", " ").slice(0, 19),
        },
      },
    })),
}));

export function mergeTasks(
  baseTasks: AutomationTask[],
  addedTasks: AutomationTask[],
  overrides: Record<string, Partial<AutomationTask>>
): AutomationTask[] {
  const merged = [...addedTasks, ...baseTasks].map((task) => ({
    ...task,
    ...overrides[task.id],
  }));
  return merged;
}
