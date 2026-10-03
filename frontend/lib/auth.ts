// Token lives in localStorage for the demo. An httpOnly cookie would be safer; the API returns the
// token as JSON today, so switching later means a cookie-setting login route, not a UI change.
const KEY = "quotepulse.token";

export function getToken(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    window.localStorage.setItem(KEY, token);
  } catch {
    // Storage blocked (private mode, disabled site data): the session simply won't persist.
  }
}

export function clearToken(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    // Nothing to clear.
  }
}
