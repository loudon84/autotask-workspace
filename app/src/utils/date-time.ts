export const BEIJING_TIME_ZONE = "Asia/Shanghai";

const legacyDateTimePattern =
  /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})(?::(\d{2}))?(?:\.\d{1,9})?$/;

const beijingDateTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  day: "2-digit",
  hour: "2-digit",
  hourCycle: "h23",
  minute: "2-digit",
  month: "2-digit",
  second: "2-digit",
  timeZone: BEIJING_TIME_ZONE,
  year: "numeric",
});

/**
 * 将服务端时间统一显示为北京时间。服务端返回的带时区时间会被转换；
 * 旧 Mock 数据中的无时区时间按已有北京时间处理，避免重复增加八小时。
 */
export function formatBeijingDateTime(
  value: Date | null | string | undefined
): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) {
      return "-";
    }

    const legacyMatch = legacyDateTimePattern.exec(trimmed);
    if (legacyMatch) {
      const [, date, hourMinute, second = "00"] = legacyMatch;
      return `${date} ${hourMinute}:${second}`;
    }

    const date = new Date(trimmed);
    return Number.isNaN(date.getTime())
      ? trimmed
      : beijingDateTimeFormatter.format(date).replaceAll("/", "-");
  }

  return Number.isNaN(value.getTime())
    ? "-"
    : beijingDateTimeFormatter.format(value).replaceAll("/", "-");
}
