import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import * as pickedEventStore from "@/lib/calendar/pickedEventStore";
import { RecommendCalendarContext } from "./RecommendCalendarContext";

vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: vi.fn() },
}));

const mockedGet = vi.mocked(apiClient.GET);

const event = {
  google_event_id: "e1",
  title: "Dinner with Sam",
  start: "2026-08-01T19:30:00Z",
  location: "Tanto",
};

describe("RecommendCalendarContext", () => {
  beforeEach(() => {
    mockedGet.mockReset();
    pickedEventStore.reset();
  });

  it("renders the unpicked prompt and hydrates the store when nothing has been checked yet", async () => {
    mockedGet.mockResolvedValue({ data: { picked: false, event: null }, error: undefined } as never);
    render(<RecommendCalendarContext />);
    await waitFor(() => expect(screen.getByText("Style for an event from calendar")).toBeInTheDocument());
    expect(screen.getByRole("link")).toHaveAttribute("href", "/calendar");
    expect(mockedGet).toHaveBeenCalledTimes(1);
  });

  it("renders the picked event's title with a Change link once hydrated", async () => {
    mockedGet.mockResolvedValue({
      data: { picked: true, event },
      error: undefined,
    } as never);
    render(<RecommendCalendarContext />);
    await waitFor(() => expect(screen.getByText(/Styling for Dinner with Sam · Change/)).toBeInTheDocument());
    expect(screen.getByRole("link")).toHaveAttribute("href", "/calendar");
  });

  it("renders the current pick immediately when the store is already loaded — no fetch, no flash", () => {
    // The regression this feature fixes: a pick confirmed elsewhere (e.g. CalendarPage's
    // handlePick) is already in the store by the time this component mounts — it must render
    // correctly on the very first paint, not after a GET resolves.
    pickedEventStore.set(event);
    render(<RecommendCalendarContext />);
    expect(screen.getByText(/Styling for Dinner with Sam · Change/)).toBeInTheDocument();
    expect(mockedGet).not.toHaveBeenCalled();
  });

  it("does not hydrate a second time once the store is already loaded", () => {
    pickedEventStore.set(null);
    render(<RecommendCalendarContext />);
    expect(screen.getByText("Style for an event from calendar")).toBeInTheDocument();
    expect(mockedGet).not.toHaveBeenCalled();
  });
});
