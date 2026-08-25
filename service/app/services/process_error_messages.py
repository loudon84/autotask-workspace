"""流程实例面向客服的错误文案（中文）。

Flow / Engine 仍可能返回英文 safe_message；落库与展示时优先按错误码翻译。
"""

from __future__ import annotations

# 常见 RPA / 流程错误码 → 客服可读说明
PROCESS_ERROR_MESSAGES_ZH: dict[str, str] = {
    "ORDER_SIGN_STATUS_UNCONFIRMED": "签章后未能确认订单回复状态（未识别为「待回签」或「已回签」），请打开 SRM 核对后重试或联系技术支持",
    "ORDER_SIGN_OUTCOME_UNKNOWN": "签章结果无法自动确认，请在 SRM 人工核对订单状态后再继续",
    "ORDER_NOT_EDITABLE": "订单当前不可编辑交货日期（可能已非待签章或页面状态变化）",
    "ORDER_LINE_SAVE_UNCONFIRMED": "交货日期保存后未能确认写入结果",
    "ORDER_DATE_FILL_FAILED": "填写交货日期失败，请重试该行",
    "ORDER_DETAIL_LINES_UNAVAILABLE": "无法读取订单行明细，请检查门户页面或附件",
    "ORDER_ATTACHMENT_LINE_DUPLICATE": "订单附件存在重复行号，请检查附件数据",
    "ERP_ORDER_IMPORT_ROW_FAILED": "创建 SDMS 销售订单时行级导入失败",
    "PROCESS_OUTPUT_LINES_MISSING": "建单成功但缺少订单行输出，无法继续填交期",
    "PROCESS_BINDING_MISSING": "当前门户未配置对应流程 Binding",
    "SRM_LOGIN_PAGE_UNAVAILABLE": "无法打开或识别 SRM 登录页",
    "SRM_LOGIN_FAILED": "SRM 登录失败，请检查账号或验证码",
    "ORDER_NOT_SIGNED": "订单尚未「已回签」，不能下载双方签章合同",
    "SIGNED_CONTRACT_BUTTON_MISSING": "已回签订单缺少「查看签章」入口，无法下载双方签章合同",
    "SIGNED_CONTRACT_WRONG_FILE": "下载到的是订单文件而非双方签章合同，请检查门户「查看签章」入口",
    "REPLY_STATUS_CHECK_FAILED": "查询回签状态失败，将在下一轮轮询重试",
}


def localize_process_error(
    error_code: str | None,
    error_message: str | None,
    *,
    fallback: str = "执行失败，请查看下方子任务详情或联系技术支持",
) -> tuple[str | None, str | None]:
    """返回 (error_code, 中文说明)。无码无文案时两者均可为 None。"""
    code = (error_code or "").strip() or None
    raw = (error_message or "").strip() or None
    if code and code in PROCESS_ERROR_MESSAGES_ZH:
        return code, PROCESS_ERROR_MESSAGES_ZH[code]
    if raw:
        # 已是中文或未知英文：有码时附带通用说明，避免纯英文吓客服
        if code and _looks_mostly_english(raw):
            return code, f"{fallback}（原始说明：{raw}）"
        return code, raw
    if code:
        return code, fallback
    return None, None


def _looks_mostly_english(text: str) -> bool:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    ascii_letters = sum(1 for ch in letters if ord(ch) < 128)
    return ascii_letters / len(letters) >= 0.8
