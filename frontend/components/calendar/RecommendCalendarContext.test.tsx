import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import { RecommendCalendarContext } from "./RecommendCalendarContext";

vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: vi.fn() },
}));

const mockedGet = vi.mocked(apiClient.GET);

describe("RecommendCalendarContext", () => {
  beforeEach(() => {
    mockedGet.mockReset();
  });

  it("renders the unpicked prompt when no event is picked", async () => {
    mockedGet.mockResolvedValue({ data: { picked: false, event: null }, error: undefined } as never);
    render(<RecommendCalendarContext />);
    await waitFor(() => expect(screen.getByText("Style for an event from calendar")).toBeInTheDocument());
    expect(screen.getByRole("link")).toHaveAttribute("href", "/calendar");
  });

  it("renders the picked event's title with a Change link", async () => {
    mockedGet.mockResolvedValue({
      data: { picked: true, event: { google_event_id: "e1", title: "Dinner with Sam", start: "2026-08-01T19:30:00Z", location: "Tanto" } },
      error: undefined,
    } as never);
    render(<RecommendCalendarContext />);
    await waitFor(() => expect(screen.getByText(/Styling for Dinner with Sam · Change/)).toBeInTheDocument());
    expect(screen.getByRole("link")).toHaveAttribute("href", "/calendar");
  });
});
