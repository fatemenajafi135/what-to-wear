import { apiClient, unwrap } from "./client";
import type { components } from "./schema";

export type ProfileResponse = components["schemas"]["ProfileResponse"];
export type StylePreferencesUpdate = components["schemas"]["StylePreferencesUpdate"];
export type BodySizeUpdate = components["schemas"]["BodySizeUpdate"];
export type NotificationsUpdate = components["schemas"]["NotificationsUpdate"];

export async function getProfile(): Promise<ProfileResponse> {
  return unwrap(await apiClient.GET("/api/v1/profile"));
}

export async function updateStylePreferences(update: StylePreferencesUpdate): Promise<ProfileResponse> {
  return unwrap(await apiClient.PATCH("/api/v1/profile/style-preferences", { body: update }));
}

export async function updateBodySize(update: BodySizeUpdate): Promise<ProfileResponse> {
  return unwrap(await apiClient.PATCH("/api/v1/profile/body-size", { body: update }));
}

export async function updateNotifications(update: NotificationsUpdate): Promise<ProfileResponse> {
  return unwrap(await apiClient.PATCH("/api/v1/profile/notifications", { body: update }));
}
