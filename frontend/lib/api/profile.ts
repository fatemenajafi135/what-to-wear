import { apiFetch } from "./client";
import type { components } from "./schema";

export type ProfileResponse = components["schemas"]["ProfileResponse"];
export type StylePreferencesUpdate = components["schemas"]["StylePreferencesUpdate"];
export type BodySizeUpdate = components["schemas"]["BodySizeUpdate"];
export type NotificationsUpdate = components["schemas"]["NotificationsUpdate"];

export function getProfile(): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>("/api/v1/profile", "GET");
}

export function updateStylePreferences(update: StylePreferencesUpdate): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>("/api/v1/profile/style-preferences", "PATCH", update);
}

export function updateBodySize(update: BodySizeUpdate): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>("/api/v1/profile/body-size", "PATCH", update);
}

export function updateNotifications(update: NotificationsUpdate): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>("/api/v1/profile/notifications", "PATCH", update);
}
