import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import * as connectionHook from "@/lib/calendar/useCalendarConnection";
import * as primed from "@/lib/calendar/primed";
import CalendarPage from "./page";

vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: vi.fn(), PUT: vi.fn() },
}));
vi.mock("@/lib/calendar/useCalendarConnection");

const mockedGet = vi.mocked(apiClient.GET);
const mockedUseCalendarConnection = vi.mocked(connectionHook.useCalendarConnection);

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
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
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
