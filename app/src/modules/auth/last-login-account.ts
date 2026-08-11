const LAST_LOGIN_ACCOUNT_KEY = "autotask:last-login-account";
const LEGACY_LAST_LOGIN_EMAIL_KEY = "autotask:last-login-email";

export function getLastLoginAccount(): string {
  try {
    return (
      localStorage.getItem(LAST_LOGIN_ACCOUNT_KEY) ??
      localStorage.getItem(LEGACY_LAST_LOGIN_EMAIL_KEY) ??
      ""
    );
  } catch {
    return "";
  }
}

export function saveLastLoginAccount(account: string): void {
  try {
    localStorage.setItem(LAST_LOGIN_ACCOUNT_KEY, account);
  } catch {
    // ignore
  }
}
