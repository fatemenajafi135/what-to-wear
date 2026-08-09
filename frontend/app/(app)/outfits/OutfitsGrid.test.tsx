import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { OutfitsGrid } from "./OutfitsGrid";

vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() },
}));
vi.mock("@/lib/useOnlineStatus", () => ({ useOnlineStatus: vi.fn(() => true) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  });
  vi.mocked(apiClient.GET).mockReset();
});

type OutfitSummary = components["schemas"]["OutfitSummary"];

function outfit(overrides: Partial<OutfitSummary> = {}): OutfitSummary {
  return {
    id: "outfit-1",
    title: "Rainy day commute",
    match_label: "great",
    favorite: false,
    created_at: new Date().toISOString(),
    item_thumbnails: [],
    item_count: 2,
    ...overrides,
  };
}

describe("OutfitsGrid", () => {
  it("shows a loading skeleton before the response resolves", () => {
    vi.mocked(apiClient.GET).mockReturnValue(new Promise(() => {}) as never);
    const { container } = render(<OutfitsGrid />);
    expect(container.querySelectorAll(".skeleton").length).toBeGreaterThan(0);
  });

  it("shows the first-run empty state and a link to Styling when there are no outfits", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: { outfits: [], total: 0, has_more: false },
      error: undefined,
      response: new Response(),
    });
    render(<OutfitsGrid />);
    expect(await screen.findByText(/No outfits yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Styling" })).toHaveAttribute("href", "/recommend");
  });

  it("shows the error state and retries on click", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({ data: undefined, error: {}, response: new Response() });
    render(<OutfitsGrid />);
    expect(await screen.findByText("Couldn't load your outfits.")).toBeInTheDocument();

    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: { outfits: [outfit()], total: 1, has_more: false },
      error: undefined,
      response: new Response(),
    });
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Rainy day commute")).toBeInTheDocument();
  });

  it("renders every saved outfit with its title and match label", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: {
        outfits: [outfit({ id: "a", title: "First" }), outfit({ id: "b", title: "Second", match_label: "good" })],
        total: 2,
        has_more: false,
      },
      error: undefined,
      response: new Response(),
    });
    render(<OutfitsGrid />);
    expect(await screen.findByText("First")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();
    expect(screen.getByText("Great match")).toBeInTheDocument();
    expect(screen.getByText("Good match")).toBeInTheDocument();
  });

  it("shows the TopHeader subtitle from the response's total, not the loaded page size", async () => {
    // gh-28: with pagination, only one page is ever loaded — the visible
    // count must come from `total`, not `outfits.length`.
    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: { outfits: [outfit()], total: 25, has_more: true },
      error: undefined,
      response: new Response(),
    });
    render(<OutfitsGrid />);
    expect(await screen.findByText("25 outfits")).toBeInTheDocument();
  });

  it("shows a +N chip and links it to Outfit detail when an outfit has more than 4 items", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: { outfits: [outfit({ item_count: 5 })], total: 1, has_more: false },
      error: undefined,
      response: new Response(),
    });
    render(<OutfitsGrid />);
    const chip = await screen.findByText("+2");
    expect(chip.closest("a")).toHaveAttribute("href", "/outfits/outfit-1");
  });

  it("does not show a +N chip for 4 or fewer items", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: { outfits: [outfit({ item_count: 4 })], total: 1, has_more: false },
      error: undefined,
      response: new Response(),
    });
    render(<OutfitsGrid />);
    await screen.findByText("Rainy day commute");
    expect(screen.queryByText(/^\+\d+$/)).not.toBeInTheDocument();
  });

  it("tapping the title switches to an inline input, and Done commits the rename", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: { outfits: [outfit()], total: 1, has_more: false },
      error: undefined,
      response: new Response(),
    });
    render(<OutfitsGrid />);
    await screen.findByText("Rainy day commute");

    await userEvent.click(screen.getByText("Rainy day commute"));
    const input = screen.getByLabelText("Outfit title");
    await userEvent.clear(input);
    await userEvent.type(input, "Friday client dinner");

    vi.mocked(apiClient.PATCH).mockResolvedValueOnce({
      data: { id: "outfit-1", title: "Friday client dinner" },
      error: undefined,
      response: new Response(),
    });
    await userEvent.click(screen.getByText("Done"));

    await waitFor(() => expect(screen.getByText("Friday client dinner")).toBeInTheDocument());
  });

  it("tapping the heart toggles favorite via the API and updates the icon label", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: { outfits: [outfit({ favorite: false })], total: 1, has_more: false },
      error: undefined,
      response: new Response(),
    });
    render(<OutfitsGrid />);
    await screen.findByText("Rainy day commute");

    vi.mocked(apiClient.POST).mockResolvedValueOnce({ data: { favorite: true }, error: undefined, response: new Response() });
    await userEvent.click(screen.getByLabelText("Save outfit"));

    await waitFor(() => expect(screen.getByLabelText("Unsave outfit")).toBeInTheDocument());
  });

  describe("pagination (gh-28)", () => {
    it("shows Load more when has_more is true, and not when it's false", async () => {
      vi.mocked(apiClient.GET).mockResolvedValueOnce({
        data: { outfits: [outfit()], total: 25, has_more: true },
        error: undefined,
        response: new Response(),
      });
      render(<OutfitsGrid />);
      expect(await screen.findByRole("button", { name: "Load more" })).toBeInTheDocument();
    });

    it("does not show Load more when has_more is false", async () => {
      vi.mocked(apiClient.GET).mockResolvedValueOnce({
        data: { outfits: [outfit()], total: 1, has_more: false },
        error: undefined,
        response: new Response(),
      });
      render(<OutfitsGrid />);
      await screen.findByText("Rainy day commute");
      expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
    });

    it("clicking Load more requests the next offset and appends the results", async () => {
      vi.mocked(apiClient.GET).mockResolvedValueOnce({
        data: { outfits: [outfit({ id: "a", title: "First" })], total: 2, has_more: true },
        error: undefined,
        response: new Response(),
      });
      render(<OutfitsGrid />);
      await screen.findByText("First");

      vi.mocked(apiClient.GET).mockResolvedValueOnce({
        data: { outfits: [outfit({ id: "b", title: "Second" })], total: 2, has_more: false },
        error: undefined,
        response: new Response(),
      });
      await userEvent.click(screen.getByRole("button", { name: "Load more" }));

      expect(await screen.findByText("Second")).toBeInTheDocument();
      expect(screen.getByText("First")).toBeInTheDocument(); // appended, not replaced
      expect(vi.mocked(apiClient.GET)).toHaveBeenLastCalledWith(
        "/api/v1/recommend/outfits",
        expect.objectContaining({ params: { query: { sort: "date", offset: 1 } } }),
      );
      // has_more flipped to false on the second page — the button is gone.
      expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
    });

    it("a dropped connection during Load more leaves the button available instead of erroring", async () => {
      // ClosetGrid.tsx:97 — offline/dropped connections during the
      // secondary "Load more" action must not surface the screen-level
      // error state; the button just stays available to retry.
      vi.mocked(apiClient.GET).mockResolvedValueOnce({
        data: { outfits: [outfit()], total: 25, has_more: true },
        error: undefined,
        response: new Response(),
      });
      render(<OutfitsGrid />);
      await screen.findByRole("button", { name: "Load more" });

      vi.mocked(apiClient.GET).mockRejectedValueOnce(new TypeError("Failed to fetch"));
      await userEvent.click(screen.getByRole("button", { name: "Load more" }));

      await waitFor(() => expect(screen.getByRole("button", { name: "Load more" })).toBeInTheDocument());
      expect(screen.queryByText("Couldn't load your outfits.")).not.toBeInTheDocument();
    });
  });
});
