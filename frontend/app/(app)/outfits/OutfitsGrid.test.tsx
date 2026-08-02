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
    vi.mocked(apiClient.GET).mockResolvedValueOnce({ data: { outfits: [] }, error: undefined, response: new Response() });
    render(<OutfitsGrid />);
    expect(await screen.findByText(/No outfits yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Styling" })).toHaveAttribute("href", "/recommend");
  });

  it("shows the error state and retries on click", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({ data: undefined, error: {}, response: new Response() });
    render(<OutfitsGrid />);
    expect(await screen.findByText("Couldn't load your outfits.")).toBeInTheDocument();

    vi.mocked(apiClient.GET).mockResolvedValueOnce({ data: { outfits: [outfit()] }, error: undefined, response: new Response() });
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Rainy day commute")).toBeInTheDocument();
  });

  it("renders every saved outfit with its title and match label", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: { outfits: [outfit({ id: "a", title: "First" }), outfit({ id: "b", title: "Second", match_label: "good" })] },
      error: undefined,
      response: new Response(),
    });
    render(<OutfitsGrid />);
    expect(await screen.findByText("First")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();
    expect(screen.getByText("Great match")).toBeInTheDocument();
    expect(screen.getByText("Good match")).toBeInTheDocument();
  });

  it("shows a +N chip and links it to Outfit detail when an outfit has more than 4 items", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: { outfits: [outfit({ item_count: 5 })] },
      error: undefined,
      response: new Response(),
    });
    render(<OutfitsGrid />);
    const chip = await screen.findByText("+2");
    expect(chip.closest("a")).toHaveAttribute("href", "/outfits/outfit-1");
  });

  it("does not show a +N chip for 4 or fewer items", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({
      data: { outfits: [outfit({ item_count: 4 })] },
      error: undefined,
      response: new Response(),
    });
    render(<OutfitsGrid />);
    await screen.findByText("Rainy day commute");
    expect(screen.queryByText(/^\+\d+$/)).not.toBeInTheDocument();
  });

  it("tapping the title switches to an inline input, and Done commits the rename", async () => {
    vi.mocked(apiClient.GET).mockResolvedValueOnce({ data: { outfits: [outfit()] }, error: undefined, response: new Response() });
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
    vi.mocked(apiClient.GET).mockResolvedValueOnce({ data: { outfits: [outfit({ favorite: false })] }, error: undefined, response: new Response() });
    render(<OutfitsGrid />);
    await screen.findByText("Rainy day commute");

    vi.mocked(apiClient.POST).mockResolvedValueOnce({ data: { favorite: true }, error: undefined, response: new Response() });
    await userEvent.click(screen.getByLabelText("Save outfit"));

    await waitFor(() => expect(screen.getByLabelText("Unsave outfit")).toBeInTheDocument());
  });
});
