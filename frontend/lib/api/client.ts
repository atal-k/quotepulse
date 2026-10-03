import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "@/lib/api/schema";
import { clearToken, getToken } from "@/lib/auth";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const api = createClient<paths>({ baseUrl: API_URL });

const auth: Middleware = {
  onRequest({ request }) {
    const token = getToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
  onResponse({ response }) {
    // An expired or revoked token sends the user back to sign-in.
    const onLogin = window.location.pathname.startsWith("/login");
    if (response.status === 401 && !onLogin) {
      clearToken();
      // Full reload on purpose: it clears the query cache along with the session.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/login");
    }
    return response;
  },
};
api.use(auth);

/** The backend's error envelope is {error: {code, message, details}}. */
export function errorMessage(error: unknown, fallback = "Something went wrong."): string {
  if (error && typeof error === "object" && "error" in error) {
    const message = (error as { error?: { message?: unknown } }).error?.message;
    if (typeof message === "string") return message;
  }
  return fallback;
}
