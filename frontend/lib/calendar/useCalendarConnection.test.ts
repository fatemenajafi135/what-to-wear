import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import { useCalendarConnection } from "./useCalendarConnection";

vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));

const mockedGet = vi.mocked(apiClient.GET);
const mockedPost = vi.mocked(apiClient.POST);

describe("useCalendarConnection", () => {
  beforeEach(() => {
    mockedGet.mockReset();
    mockedPost.mockReset();
  });

  it("loads connection state on mount", async () => {
    mockedGet.mockResolvedValue({ data: { connected: true, connected_at: "2026-07-20T10:00:00Z" }, error: undefined } as never);

    const { result } = renderHook(() => useCalendarConnection());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.connected).toBe(true);
    expect(result.current.connectedAt).toBe("2026-07-20T10:00:00Z");
    expect(mockedGet).toHaveBeenCalledWith("/api/v1/calendar/connection");
  });

  it("connect() redirects to the authorize URL returned by the backend", async () => {
    mockedGet.mockResolvedValue({ data: { connected: false, connected_at: null }, error: undefined } as never);
    mockedPost.mockResolvedValue({ data: { authorize_url: "https://accounts.google.com/authorize" }, error: undefined } as never);
    const assign = vi.fn();
    Object.defineProperty(window, "location", { value: { assign }, writable: true });

    const { result } = renderHook(() => useCalendarConnection());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.connect();
    });

    expect(mockedPost).toHaveBeenCalledWith("/api/v1/calendar/connect/start");
    expect(assign).toHaveBeenCalledWith("https://accounts.google.com/authorize");
  });

  it("disconnect() updates state to disconnected on success", async () => {
    mockedGet.mockResolvedValue({ data: { connected: true, connected_at: "2026-07-20T10:00:00Z" }, error: undefined } as never);
    mockedPost.mockResolvedValue({ data: { connected: false, connected_at: null }, error: undefined } as never);

    const { result } = renderHook(() => useCalendarConnection());
    await waitFor(() => expect(result.current.connected).toBe(true));

    let ok = false;
    await act(async () => {
      ok = await result.current.disconnect();
    });

    expect(ok).toBe(true);
    expect(result.current.connected).toBe(false);
    expect(result.current.connectedAt).toBeNull();
  });

  it("disconnect() leaves state unchanged when the request fails", async () => {
    mockedGet.mockResolvedValue({ data: { connected: true, connected_at: "2026-07-20T10:00:00Z" }, error: undefined } as never);
    mockedPost.mockResolvedValue({ data: undefined, error: { detail: "boom" } } as never);

    const { result } = renderHook(() => useCalendarConnection());
    await waitFor(() => expect(result.current.connected).toBe(true));

    let ok = true;
    await act(async () => {
      ok = await result.current.disconnect();
    });

    expect(ok).toBe(false);
    expect(result.current.connected).toBe(true);
  });
});
