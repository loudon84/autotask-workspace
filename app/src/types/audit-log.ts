export interface AuditLog {
  id: string;
  taskId: string;
  action: string;
  operator: string;
  detail: string;
  createdAt: string;
}
