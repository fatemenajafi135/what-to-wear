import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { components } from "@/lib/api/schema";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));

import { apiClient } from "@/lib/api/client";
import { SuggestionPager } from "./SuggestionPager";

type StylingOutfit = components["schemas"]["StylingOutfit"];

// design-decisions.md §42/§43: every outfit is already saved by the time
// this component ever sees it (`id` is always present, never a not-yet-
// saved placeholder) — but "saved" and "favorite" are independent, and a
// fresh outfit's real default is unfavorited, so that's the fixture default
// here too. Individual tests override it where the favorited state matters.
function outfit(overrides: Partial<StylingOutfit> = {}): StylingOutfit {
  return {
    id: "outfit-1",
    occasion: "Rainy day commute",
    rationale_text: "A cohesive look.",
    items: [{ id: "item-1", name: "Coat", category: "outerwear", category_group: "outerwear", colors: [], color_names: [], photo_url: null, photo_background_color: null }],
    match_label: "great",
    meta_line: "Rainy day commute · rain",
    favorite: false,
    ...overrides,
  };
}

function matchMediaMock(matches: boolean) {
  return vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
}

beforeEach(() => {
  vi.mocked(apiClient.POST).mockReset();
  push.mockReset();
  window.matchMedia = matchMediaMock(false);
});

describe("SuggestionPager", () => {
  it("renders one card per outfit with a working '1 of N' indicator", () => {
    render(<SuggestionPager outfits={[outfit(), outfit({ occasion: "Second" }), outfit({ occasion: "Third" })]} />);
    expect(screen.getByText("1 of 3")).toBeInTheDocument();
  });

  it("renders a single card with no indicator/arrows when there is exactly one outfit", () => {
    render(<SuggestionPager outfits={[outfit()]} />);
    expect(screen.queryByText(/of 1/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Next suggestion")).not.toBeInTheDocument();
  });

  it("renders nothing for an empty outfits array", () => {
    const { container } = render(<SuggestionPager outfits={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("advancing the pager updates the indicator", async () => {
    const user = userEvent.setup();
    render(<SuggestionPager outfits={[outfit(), outfit({ occasion: "Second" }), outfit({ occasion: "Third" })]} />);

    await user.click(screen.getByLabelText("Next suggestion"));
    expect(screen.getByText("2 of 3")).toBeInTheDocument();
  });

  it("renders the heart from outfit.favorite directly — saved and favorited are independent", () => {
    // design-decisions.md §43: every outfit is already saved, but a fresh
    // one is typically unfavorited (the real backend default) — the heart
    // must reflect favorite, not "is this saved" (every card here always is).
    const { rerender } = render(<SuggestionPager outfits={[outfit({ favorite: false })]} />);
    expect(screen.getByLabelText("Save outfit")).toBeInTheDocument();

    rerender(<SuggestionPager outfits={[outfit({ favorite: true })]} />);
    expect(screen.getByLabelText("Unsave outfit")).toBeInTheDocument();
  });

  it("tapping the heart toggles favorite via the outfit's own id — no create call at all", async () => {
    vi.mocked(apiClient.POST).mockResolvedValueOnce({
      data: { id: "outfit-1", favorite: false },
      error: undefined,
      response: new Response(),
    } as never);
    const user = userEvent.setup();
    render(<SuggestionPager outfits={[outfit({ id: "outfit-1", favorite: true })]} />);

    await user.click(screen.getByLabelText("Unsave outfit"));

    expect(apiClient.POST).toHaveBeenCalledTimes(1);
    expect(apiClient.POST).toHaveBeenCalledWith(
      "/api/v1/recommend/outfits/{outfit_id}/favorite",
      expect.objectContaining({ params: { path: { outfit_id: "outfit-1" } } }),
    );
    expect(await screen.findByLabelText("Save outfit")).toBeInTheDocument();
  });

  it("tapping the card body navigates to /outfits/:id immediately, no save step first", async () => {
    const user = userEvent.setup();
    render(<SuggestionPager outfits={[outfit({ id: "outfit-1" })]} />);

    await user.click(screen.getByText("Rainy day commute"));

    expect(push).toHaveBeenCalledWith("/outfits/outfit-1");
    expect(apiClient.POST).not.toHaveBeenCalled();
  });

  it("never calls the API for feedback thumbs", async () => {
    const user = userEvent.setup();
    render(<SuggestionPager outfits={[outfit()]} />);

    await user.click(screen.getByLabelText("Helpful"));
    await user.click(screen.getByLabelText("Not helpful"));

    expect(apiClient.POST).not.toHaveBeenCalled();
  });
});
