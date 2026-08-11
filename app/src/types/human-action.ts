export type HumanActionType =
  | "manual_confirm"
  | "manual_upload"
  | "manual_approve"
  | "manual_captcha"
  | "manual_mfa"
  | "manual_exception_handle";

export type HumanActionStatus =
  | "PENDING"
  | "OPENED"
  | "CONFIRMED"
  | "CANCELLED"
  | "EXPIRED";

export interface HumanAction {
  id: string;
  taskId: string;
  runId?: string;
  portalId?: string;

  type: HumanActionType;
  targetUrl: string;
  instruction: string;

  status: HumanActionStatus;

  createdAt: string;
  openedAt?: string;
  confirmedAt?: string;
  confirmedBy?: string;
  note?: string;
}
