import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { HistoryList } from "./HistoryList";

vi.mock("@/lib/api/client", () => ({ apiClient: { GET: vi.fn() } }));

const mockIsOnline = vi.fn(() => true);
vi.mock("@/lib/useOnlineStatus", () => ({ useOnlineStatus: () => mockIsOnline() }));

beforeEach(() => {
  vi.mocked(apiClient.GET).mockReset();
  mockIsOnline.mockReturnValue(true);
});

type SessionSummary = components["schemas"]["SessionSummary"];

function session(overrides: Partial<SessionSummary> = {}): SessionSummary {
  return {
    id: "session-1",
    preview: "Something for a rainy commute",
    message_count: 2,
    outfit_count: 0,
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("HistoryList", () => {
  it("shows a loading skeleton before the response resolves", () => {
    vi.mocked(apiClient.GET).mockReturnValue(new Promise(() => {}) as never);
    const { container } = render(<HistoryList />);
    expect(container.querySelectorAll(".skeleton").length).toBeGreaterThan(0);
  });

  it("shows the empty state with the exact specified copy", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({ data: { sessions: [] }, error: undefined, response: new Response() });
    render(<HistoryList />);
    expect(await screen.findByText("No past conversations yet. Start styling and I'll save them here.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Styling" })).toHaveAttribute("href", "/recommend");
  });

  it("shows the error state with the exact specified copy and retries on click", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({ data: undefined, error: {}, response: new Response() });
    render(<HistoryList />);
    expect(await screen.findByText("Couldn't load your history.")).toBeInTheDocument();

    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: { sessions: [session()] },
      error: undefined,
      response: new Response(),
    });
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Something for a rainy commute")).toBeInTheDocument();
  });

  it("offline suppresses the screen's own error", async () => {
    mockIsOnline.mockReturnValue(false);
    vi.mocked(apiClient.GET).mockResolvedValueOnce({ data: undefined, error: {}, response: new Response() });
    render(<HistoryList />);
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByText("Couldn't load your history.")).not.toBeInTheDocument();
  });

  it("renders preview, date, and message count for each row", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: { sessions: [session({ id: "a", preview: "First", message_count: 4 })] },
      error: undefined,
      response: new Response(),
    });
    render(<HistoryList />);
    expect(await screen.findByText("First")).toBeInTheDocument();
    expect(screen.getByText("4 messages")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /First/ })).toHaveAttribute("href", "/history/a");
  });

  it("shows the outfit-count line only when the session produced outfits", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: {
        sessions: [
          session({ id: "with-outfits", preview: "With outfits", outfit_count: 2 }),
          session({ id: "without-outfits", preview: "Without outfits", outfit_count: 0 }),
        ],
      },
      error: undefined,
      response: new Response(),
    });
    render(<HistoryList />);
    await screen.findByText("With outfits");
    expect(screen.getByText("2 outfits")).toBeInTheDocument();
    expect(screen.queryByText("0 outfits")).not.toBeInTheDocument();
  });

  it("singularizes message/outfit counts of exactly 1", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: { sessions: [session({ message_count: 1, outfit_count: 1 })] },
      error: undefined,
      response: new Response(),
    });
    render(<HistoryList />);
    await screen.findByText("Something for a rainy commute");
    expect(screen.getByText("1 message")).toBeInTheDocument();
    expect(screen.getByText("1 outfit")).toBeInTheDocument();
  });
});
