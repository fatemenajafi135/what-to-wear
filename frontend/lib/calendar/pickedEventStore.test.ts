import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: vi.fn() },
}));

import { apiClient } from "@/lib/api/client";
import { getServerSnapshot, getState, hydrate, reset, set, subscribe } from "./pickedEventStore";

const mockedGet = vi.mocked(apiClient.GET);

const event = {
  google_event_id: "e1",
  title: "Dinner with Ana",
  start: "2026-08-14T19:00:00Z",
  location: "Tanto",
};

beforeEach(() => {
  reset();
  mockedGet.mockReset();
});

describe("pickedEventStore", () => {
  it("starts unknown, with no event", () => {
    expect(getState()).toEqual({ status: "unknown", event: null });
    expect(getServerSnapshot()).toEqual({ status: "unknown", event: null });
  });

  it("hydrate() issues exactly one GET and writes the result", async () => {
    mockedGet.mockResolvedValue({ data: { picked: true, event }, error: undefined } as never);
    hydrate();
    await vi.waitFor(() => expect(getState().status).toBe("loaded"));
    expect(getState().event).toEqual(event);
    expect(mockedGet).toHaveBeenCalledTimes(1);
  });

  it("hydrate() writes null when nothing is picked", async () => {
    mockedGet.mockResolvedValue({ data: { picked: false, event: null }, error: undefined } as never);
    hydrate();
    await vi.waitFor(() => expect(getState().status).toBe("loaded"));
    expect(getState().event).toBeNull();
  });

  it("a second concurrent hydrate() call does not issue a second GET", async () => {
    let resolve: (value: unknown) => void = () => {};
    mockedGet.mockReturnValue(new Promise((r) => (resolve = r)) as never);
    hydrate();
    hydrate();
    resolve({ data: { picked: true, event }, error: undefined });
    await vi.waitFor(() => expect(getState().status).toBe("loaded"));
    expect(mockedGet).toHaveBeenCalledTimes(1);
  });

  it("hydrate() is a no-op once already loaded", async () => {
    set(event);
    hydrate();
    expect(mockedGet).not.toHaveBeenCalled();
  });

  it("set() updates state and notifies subscribers synchronously, with no network call", () => {
    const listener = vi.fn();
    subscribe(listener);
    set(event);
    expect(getState()).toEqual({ status: "loaded", event });
    expect(listener).toHaveBeenCalledTimes(1);
    expect(mockedGet).not.toHaveBeenCalled();
  });

  it("set(null) clears the picked event", () => {
    set(event);
    set(null);
    expect(getState()).toEqual({ status: "loaded", event: null });
  });

  it("subscribe() returns a working unsubscribe function", () => {
    const listener = vi.fn();
    const unsubscribe = subscribe(listener);
    unsubscribe();
    set(event);
    expect(listener).not.toHaveBeenCalled();
  });
});
