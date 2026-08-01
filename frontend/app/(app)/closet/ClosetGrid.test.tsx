import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { ClosetGrid } from "./ClosetGrid";

vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: vi.fn() },
}));
vi.mock("@/lib/useOnlineStatus", () => ({ useOnlineStatus: vi.fn(() => true) }));

const mockedGet = vi.mocked(apiClient.GET);

type ClosetItemView = components["schemas"]["ClosetItemView"];

function item(overrides: Partial<ClosetItemView>): ClosetItemView {
  return {
    id: "item-1",
    category: "t-shirt",
    category_group: "top",
    colors: ["#1b2a4a"],
    color_names: ["navy"],
    formality: "casual",
    warmth: 1,
    season: ["spring"],
    fabric: "cotton",
    pattern: null,
    fit: null,
    name: "Navy tee",
    notes: null,
    source: "upload",
    photo_path: null,
    photo_url: null,
    favorite: false,
    ...overrides,
  };
}

beforeEach(() => {
  mockedGet.mockReset();
});

describe("ClosetGrid", () => {
  it("renders a real photo for an item with photo_url — no diagonal-stripe placeholder", async () => {
    mockedGet.mockResolvedValueOnce({
      data: { items: [item({ id: "with-photo", photo_url: "https://example.com/signed.jpg" })], total: 1, has_more: false },
      error: undefined,
      response: new Response(),
    });

    render(<ClosetGrid />);

    const img = await screen.findByRole("link", { name: "Navy tee" });
    const photoImg = img.querySelector("img");
    expect(photoImg).not.toBeNull();
    expect(photoImg).toHaveAttribute("src", "https://example.com/signed.jpg");
  });

  it("renders the NoPhoto treatment for an item with no photo", async () => {
    mockedGet.mockResolvedValueOnce({
      data: { items: [item({ id: "no-photo", photo_url: null })], total: 1, has_more: false },
      error: undefined,
      response: new Response(),
    });

    render(<ClosetGrid />);

    const link = await screen.findByRole("link", { name: "Navy tee" });
    expect(link.querySelector("img")).toBeNull();
    expect(link.querySelector('[aria-hidden="true"]')).not.toBeNull();
  });
});
