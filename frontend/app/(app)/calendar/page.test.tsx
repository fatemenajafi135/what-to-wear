import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import * as connectionHook from "@/lib/calendar/useCalendarConnection";
import * as primed from "@/lib/calendar/primed";
import * as pickedEventStore from "@/lib/calendar/pickedEventStore";
import CalendarPage from "./page";

vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: vi.fn(), PUT: vi.fn() },
}));
vi.mock("@/lib/calendar/useCalendarConnection");

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockedGet = vi.mocked(apiClient.GET);
const mockedPut = vi.mocked(apiClient.PUT);
const mockedUseCalendarConnection = vi.mocked(connectionHook.useCalendarConnection);

const upcomingEvent = {
  google_event_id: "e1",
  title: "Dinner with Sam",
  start: new Date(Date.now() + 3_600_000).toISOString(),
  location: "Tanto",
};

function withOneEvent() {
  mockedGet.mockImplementation(async (path) => {
    if (path === "/api/v1/calendar/events") {
      return { data: { events: [upcomingEvent] }, error: undefined } as never;
    }
    return { data: { picked: false, event: null }, error: undefined } as never;
  });
}

function connectionState(overrides: Partial<connectionHook.CalendarConnectionState> = {}) {
  return {
    connected: false,
    connectedAt: null,
    isLoading: false,
    connect: vi.fn(),
    disconnect: vi.fn(),
    refresh: vi.fn(),
    ...overrides,
  };
}

beforeEach(() => {
  mockedGet.mockReset();
  mockedPut.mockReset();
  mockPush.mockReset();
  pickedEventStore.reset();
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  });
});

describe("CalendarPage — disconnected state", () => {
  it("renders the disconnected card copy", () => {
    mockedUseCalendarConnection.mockReturnValue(connectionState());
    render(<CalendarPage />);
    expect(screen.getByRole("heading", { name: "Connect your calendar" })).toBeInTheDocument();
    expect(screen.getByText(/Link Google Calendar/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect Google Calendar" })).toBeInTheDocument();
  });

  it("shows the primer on first connect attempt, then calls connect", async () => {
    vi.spyOn(primed, "isCalendarPrimed").mockReturnValue(false);
    const setPrimedSpy = vi.spyOn(primed, "setCalendarPrimed");
    const connect = vi.fn();
    mockedUseCalendarConnection.mockReturnValue(connectionState({ connect }));

    render(<CalendarPage />);
    await userEvent.click(screen.getByRole("button", { name: "Connect Google Calendar" }));

    expect(screen.getByRole("heading", { name: "Before you connect" })).toBeInTheDocument();
    expect(connect).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Continue to Google" }));
    expect(setPrimedSpy).toHaveBeenCalled();
    expect(connect).toHaveBeenCalledTimes(1);
  });

  it("skips the primer once already primed", async () => {
    vi.spyOn(primed, "isCalendarPrimed").mockReturnValue(true);
    const connect = vi.fn();
    mockedUseCalendarConnection.mockReturnValue(connectionState({ connect }));

    render(<CalendarPage />);
    await userEvent.click(screen.getByRole("button", { name: "Connect Google Calendar" }));

    expect(screen.queryByRole("heading", { name: "Before you connect" })).not.toBeInTheDocument();
    expect(connect).toHaveBeenCalledTimes(1);
  });
});

describe("CalendarPage — connected states", () => {
  it("renders the empty state with a bypass action", async () => {
    mockedUseCalendarConnection.mockReturnValue(connectionState({ connected: true }));
    mockedGet.mockImplementation(async (path) => {
      if (path === "/api/v1/calendar/events") return { data: { events: [] }, error: undefined } as never;
      return { data: { picked: false, event: null }, error: undefined } as never;
    });

    render(<CalendarPage />);
    await waitFor(() => expect(screen.getByText(/Nothing on your calendar this week/)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Style something" })).toHaveAttribute("href", "/recommend");
  });

  it("renders the error state when events fail to load", async () => {
    mockedUseCalendarConnection.mockReturnValue(connectionState({ connected: true }));
    mockedGet.mockImplementation(async (path) => {
      if (path === "/api/v1/calendar/events") return { data: undefined, error: { detail: "boom" } } as never;
      return { data: { picked: false, event: null }, error: undefined } as never;
    });

    render(<CalendarPage />);
    await waitFor(() => expect(screen.getByText("Couldn't sync your calendar.")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("renders events with computed labels, not hardcoded strings", async () => {
    mockedUseCalendarConnection.mockReturnValue(connectionState({ connected: true }));
    mockedGet.mockImplementation(async (path) => {
      if (path === "/api/v1/calendar/events") {
        return {
          data: {
            events: [
              {
                google_event_id: "e1",
                title: "Dinner with Sam",
                start: new Date(Date.now() + 3_600_000).toISOString(),
                location: "Tanto",
              },
            ],
          },
          error: undefined,
        } as never;
      }
      return { data: { picked: false, event: null }, error: undefined } as never;
    });

    render(<CalendarPage />);
    await waitFor(() => expect(screen.getByText("Dinner with Sam")).toBeInTheDocument());
    expect(screen.queryByText("Today, 7:30 PM")).not.toBeInTheDocument();
  });
});

describe("CalendarPage — picking an event (issue #41 defect 1)", () => {
  beforeEach(() => {
    mockedUseCalendarConnection.mockReturnValue(connectionState({ connected: true }));
    withOneEvent();
  });

  it("navigates to /recommend and writes through pickedEventStore once the save succeeds", async () => {
    mockedPut.mockResolvedValue({
      data: { picked: true, event: upcomingEvent },
      error: undefined,
    } as never);

    render(<CalendarPage />);
    await waitFor(() => expect(screen.getByText("Dinner with Sam")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /Dinner with Sam/ }));

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/recommend"));
    expect(pickedEventStore.getState()).toEqual({ status: "loaded", event: upcomingEvent });
  });

  it("does not navigate, re-enables rows, and shows a retryable error when the save fails", async () => {
    mockedPut.mockResolvedValue({ data: undefined, error: { detail: "boom" } } as never);

    render(<CalendarPage />);
    await waitFor(() => expect(screen.getByText("Dinner with Sam")).toBeInTheDocument());
    const row = screen.getByRole("button", { name: /Dinner with Sam/ });
    await userEvent.click(row);

    await waitFor(() => expect(screen.getByText("Couldn't save that pick.")).toBeInTheDocument());
    expect(mockPush).not.toHaveBeenCalled();
    expect(row).not.toBeDisabled();
    expect(pickedEventStore.getState()).toEqual({ status: "unknown", event: null });

    // "Try again" re-attempts the same event.
    mockedPut.mockClear();
    mockedPut.mockResolvedValue({ data: { picked: true, event: upcomingEvent }, error: undefined } as never);
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(mockedPut).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/recommend"));
  });

  it("disables every row while the pick is in flight, without marking it picked yet", async () => {
    let resolvePut: (value: unknown) => void = () => {};
    mockedPut.mockReturnValue(new Promise((resolve) => (resolvePut = resolve)) as never);

    render(<CalendarPage />);
    await waitFor(() => expect(screen.getByText("Dinner with Sam")).toBeInTheDocument());
    const row = screen.getByRole("button", { name: /Dinner with Sam/ });
    await userEvent.click(row);

    await waitFor(() => expect(row).toBeDisabled());
    expect(mockPush).not.toHaveBeenCalled();

    resolvePut({ data: { picked: true, event: upcomingEvent }, error: undefined });
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/recommend"));
  });
});
