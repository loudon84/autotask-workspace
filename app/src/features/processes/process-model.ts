import type {
  ProcessInstanceStatus,
  ProcessLineStatus,
  ProcessStage,
  ProcessSubTask,
} from "@/types/process-instance";

export const SCAN_TASK_TYPE = "srm_scan_pending_orders";
export const CUSTOMER_ORDER_PROCESS_CODE = "srm_customer_order";

export interface StageMeta {
  id: ProcessStage;
  /** 对人展示的阶段名（列表 Tab / 列 / 详情主徽章 / 进度条统一） */
  name: string;
  /** 操作按钮文案；与阶段名分离 */
  button: string | null;
}

/** 节点定义与 v2.02 §6.3 中文名对齐；按钮文案仍为动作 */
export const STAGE_DEFINITIONS: StageMeta[] = [
  { id: "CREATING_SDMS", name: "建单中", button: null },
  { id: "SDMS_CREATED", name: "待填写交期", button: "填写交货日期" },
  { id: "DATES_PARTIAL", name: "交期填写中", button: "填写交货日期" },
  { id: "DATES_COMPLETE", name: "待签章", button: "去签章" },
  { id: "SIGN_REQUESTED", name: "待回签", button: null },
  { id: "SIGNED", name: "已回签", button: "手动触发签章合同下载" },
  { id: "ARCHIVED", name: "已完成", button: null },
  { id: "FAILED", name: "失败", button: "重试" },
];

/** 主流程节点（不含失败态），用于详情页进度条 */
export const MAIN_STAGES: ProcessStage[] = [
  "CREATING_SDMS",
  "SDMS_CREATED",
  "DATES_COMPLETE",
  "SIGN_REQUESTED",
  "ARCHIVED",
];

const BLOCKING_TASK_STATUSES = new Set(["FAILED", "WAITING_HUMAN"]);

const TASK_TYPE_NODE_LABEL: Record<string, string> = {
  srm_prepare_erp_order: "建单",
  srm_fill_line_delivery_date: "填写交期",
  srm_sign_order: "签章",
  srm_upload_order_attachment: "上传附件",
  srm_check_reply_status: "回签探测",
  srm_scan_pending_orders: "扫单",
};

export interface ProcessBlocker {
  title: string;
  message: string;
  errorCode?: string | null;
}

export function stageName(stage: ProcessStage): string {
  return STAGE_DEFINITIONS.find((item) => item.id === stage)?.name ?? stage;
}

export function stageButton(stage: ProcessStage): string | null {
  return STAGE_DEFINITIONS.find((item) => item.id === stage)?.button ?? null;
}

/** 列表「操作」按钮应跳转的路径；交期填写直达编辑页，其余进详情。 */
export function stageActionPath(
  stage: ProcessStage
): "/processes/$instanceId/dates" | "/processes/$instanceId" {
  if (stage === "SDMS_CREATED" || stage === "DATES_PARTIAL") {
    return "/processes/$instanceId/dates";
  }
  return "/processes/$instanceId";
}

export function stageProgressIndex(stage: ProcessStage): number {
  if (stage === "DATES_PARTIAL") {
    return MAIN_STAGES.indexOf("SDMS_CREATED");
  }
  if (stage === "SIGNED") {
    return MAIN_STAGES.indexOf("SIGN_REQUESTED");
  }
  const index = MAIN_STAGES.indexOf(stage);
  return index >= 0 ? index : -1;
}

export function statusLabel(status: ProcessInstanceStatus): string {
  switch (status) {
    case "ACTIVE":
      return "进行中";
    case "COMPLETED":
      return "已完成";
    case "FAILED":
      return "失败";
    case "CANCELLED":
      return "已取消";
    default:
      return status;
  }
}

export function lineStatusLabel(status: ProcessLineStatus): string {
  switch (status) {
    case "PENDING":
      return "未填写";
    case "SUBMITTING":
      return "写入中";
    case "WRITTEN":
      return "已写入";
    case "WRITE_FAILED":
      return "写入失败";
    default:
      return status;
  }
}

function taskTypeNodeLabel(taskType: string): string {
  return TASK_TYPE_NODE_LABEL[taskType] ?? taskType;
}

/** 常见错误码 → 客服可读中文（与 service process_error_messages 对齐） */
const PROCESS_ERROR_MESSAGES_ZH: Record<string, string> = {
  ORDER_SIGN_STATUS_UNCONFIRMED:
    "签章后未能确认订单回复状态（未识别为「待回签」或「已回签」），请打开 SRM 核对后重试或联系技术支持",
  ORDER_SIGN_OUTCOME_UNKNOWN:
    "签章结果无法自动确认，请在 SRM 人工核对订单状态后再继续",
  ORDER_NOT_EDITABLE: "订单当前不可编辑交货日期（可能已非待签章或页面状态变化）",
  ORDER_LINE_SAVE_UNCONFIRMED: "交货日期保存后未能确认写入结果",
  ORDER_DATE_FILL_FAILED: "填写交货日期失败，请重试该行",
  ORDER_DETAIL_LINES_UNAVAILABLE: "无法读取订单行明细，请检查门户页面或附件",
  ORDER_ATTACHMENT_LINE_DUPLICATE: "订单附件存在重复行号，请检查附件数据",
  ERP_ORDER_IMPORT_ROW_FAILED: "创建 SDMS 销售订单时行级导入失败",
  PROCESS_OUTPUT_LINES_MISSING: "建单成功但缺少订单行输出，无法继续填交期",
  SRM_LOGIN_PAGE_UNAVAILABLE: "无法打开或识别 SRM 登录页",
  SRM_LOGIN_FAILED: "SRM 登录失败，请检查账号或验证码",
  REPLY_STATUS_CHECK_FAILED: "查询回签状态失败，将在下一轮轮询重试",
  ORDER_NOT_SIGNED: "订单尚未「已回签」，不能下载双方签章合同",
  SIGNED_CONTRACT_BUTTON_MISSING:
    "已回签订单缺少「查看签章」入口，无法下载双方签章合同",
  SIGNED_CONTRACT_WRONG_FILE:
    "下载到的是订单文件而非双方签章合同，请检查门户「查看签章」入口",
};

function looksMostlyEnglish(text: string): boolean {
  const letters = [...text].filter((ch) => /\p{L}/u.test(ch));
  if (letters.length === 0) {
    return false;
  }
  const ascii = letters.filter((ch) => ch.charCodeAt(0) < 128).length;
  return ascii / letters.length >= 0.8;
}

/** 列表/详情展示用：优先错误码中文，避免客服直接读英文 Flow 原文 */
export function formatProcessError(
  errorCode?: string | null,
  errorMessage?: string | null
): string {
  const code = errorCode?.trim() || "";
  const raw = errorMessage?.trim() || "";
  if (code && PROCESS_ERROR_MESSAGES_ZH[code]) {
    return PROCESS_ERROR_MESSAGES_ZH[code];
  }
  if (raw) {
    if (code && looksMostlyEnglish(raw)) {
      return `执行失败，请查看子任务详情或联系技术支持（原始说明：${raw}）`;
    }
    return raw;
  }
  return code ? "执行失败，请查看子任务详情或联系技术支持" : "";
}

/**
 * 详情卡点条：整单失败 / lastError / 当前各节点（含行）最新子任务若失败或待人工。
 * 不改变状态机——ACTIVE+待签章仍可重试。
 */
export function resolveProcessBlocker(input: {
  stage: ProcessStage;
  status: ProcessInstanceStatus;
  lastErrorCode?: string | null;
  lastErrorMessage?: string | null;
  subTasks?: ProcessSubTask[];
}): ProcessBlocker | null {
  if (input.status === "FAILED" || input.stage === "FAILED") {
    return {
      title: "流程失败",
      message:
        formatProcessError(input.lastErrorCode, input.lastErrorMessage) ||
        "实例已失败，可重试",
      errorCode: input.lastErrorCode,
    };
  }
  if (input.status !== "ACTIVE") {
    return null;
  }

  const lastError = formatProcessError(
    input.lastErrorCode,
    input.lastErrorMessage
  );
  if (lastError) {
    return {
      title: `${stageName(input.stage)}未完成`,
      message: lastError,
      errorCode: input.lastErrorCode,
    };
  }

  // 同一 taskType(+行号) 只看最新一次，避免历史失败盖住后续成功
  const latestByKey = new Map<string, ProcessSubTask>();
  for (const task of [...(input.subTasks ?? [])].sort((left, right) =>
    left.updatedAt.localeCompare(right.updatedAt)
  )) {
    const key = `${task.taskType}:${task.lineNumber ?? ""}`;
    latestByKey.set(key, task);
  }
  const blocking = [...latestByKey.values()]
    .filter((task) => BLOCKING_TASK_STATUSES.has(task.status))
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
  const task = blocking[0];
  if (!task) {
    return null;
  }
  return {
    title: `${taskTypeNodeLabel(task.taskType)}未完成`,
    message:
      task.status === "WAITING_HUMAN"
        ? "子任务等待人工处理"
        : "子任务执行失败",
  };
}

export function isLineEditable(
  stage: ProcessStage,
  status: ProcessInstanceStatus,
  lineStatus: ProcessLineStatus
): boolean {
  if (status !== "ACTIVE") {
    return false;
  }
  if (stage !== "SDMS_CREATED" && stage !== "DATES_PARTIAL") {
    return false;
  }
  return lineStatus !== "SUBMITTING";
}
