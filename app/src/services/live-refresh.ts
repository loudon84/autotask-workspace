export const LIVE_STATUS_REFRESH_INTERVAL_MS = 2000;
export const LIVE_LOG_REFRESH_INTERVAL_MS = 1000;

export function getRemoteRefreshInterval(
  isRemote: boolean,
  interval = LIVE_STATUS_REFRESH_INTERVAL_MS
): false | number {
  return isRemote ? interval : false;
}
