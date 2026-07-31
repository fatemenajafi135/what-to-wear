"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";

export interface CalendarConnectionState {
  connected: boolean;
  connectedAt: string | null;
  isLoading: boolean;
  /** Starts the PKCE flow and redirects the browser to Google's consent
   * screen. Never resolves on success — the page navigates away. */
  connect: () => Promise<void>;
  disconnect: () => Promise<boolean>;
  refresh: () => Promise<void>;
}

/**
 * The one piece of shared state both `/calendar`'s own connect action and
 * Settings → Connected accounts' Google Calendar row consume, per the
 * handoff's "two entry points, one state" requirement
 * (docs/handoffs/012-calendar.md §6.4). Reading or writing from either
 * surface goes through this hook, never a second independent fetch.
 */
export function useCalendarConnection(): CalendarConnectionState {
  const [connected, setConnected] = useState(false);
  const [connectedAt, setConnectedAt] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    const { data } = await apiClient.GET("/api/v1/calendar/connection");
    if (data) {
      setConnected(data.connected);
      setConnectedAt(data.connected_at ?? null);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const connect = useCallback(async () => {
    const { data } = await apiClient.POST("/api/v1/calendar/connect/start");
    if (data?.authorize_url) {
      window.location.assign(data.authorize_url);
    }
  }, []);

  const disconnect = useCallback(async () => {
    const { data } = await apiClient.POST("/api/v1/calendar/disconnect");
    if (data) {
      setConnected(data.connected);
      setConnectedAt(data.connected_at ?? null);
      return true;
    }
    return false;
  }, []);

  return { connected, connectedAt, isLoading, connect, disconnect, refresh };
}
