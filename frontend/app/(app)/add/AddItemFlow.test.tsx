import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import { AddItemFlow } from "./AddItemFlow";

vi.mock("@/lib/api/client", () => ({
  apiClient: { POST: vi.fn(), GET: vi.fn() },
}));
vi.mock("@/lib/useOnlineStatus", () => ({ useOnlineStatus: vi.fn(() => true) }));
vi.mock("@/lib/camera/primed", () => ({
  isCameraPrimed: vi.fn(() => true), // primed — skip the primer dialog in these flow tests
  setCameraPrimed: vi.fn(),
}));

const mockedPost = vi.mocked(apiClient.POST);
const mockedGet = vi.mocked(apiClient.GET);

beforeEach(() => {
  mockedGet.mockResolvedValue({ data: TAXONOMY, error: undefined, response: new Response() } as never);
  mockedPost.mockReset();
  URL.createObjectURL = vi.fn(() => "blob:fake-url");
});

async function selectFile() {
  const file = new File(["fake"], "shirt.jpg", { type: "image/jpeg" });
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  await userEvent.upload(input, file);
}

const TAXONOMY = {
  top: ["blouse", "shirt", "t-shirt"],
  bottom: ["jeans", "trousers"],
  full_body: ["dress"],
  outerwear: ["blazer", "coat"],
  footwear: ["boots", "sneakers"],
  accessory: ["belt", "bow_tie", "necklace", "tie"],
};

describe("AddItemFlow", () => {
  it("shows the review card pre-filled after a successful scan", async () => {
    mockedPost.mockResolvedValueOnce({
      data: {
        photo_path: "user-a/x.jpg",
        extraction_ok: true,
        extracted: {
          category: "top",
          colors: ["#1b2a4a"],
          fabric: "cotton",
          formality: "casual",
          warmth: 2,
          season: ["spring"],
          pattern: "solid",
          fit: "regular",
        },
        color_names: ["navy"],
      },
      error: undefined,
      response: new Response(),
    });

    render(<AddItemFlow onClose={vi.fn()} />);
    await selectFile();

    expect(await screen.findByRole("button", { name: "Top" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Fabric")).toHaveValue("cotton");
    // Hex, shown as colour — the swatch and the literal code, not a name.
    expect(screen.getByLabelText("Color 1")).toHaveValue("#1b2a4a");
    expect(screen.getByRole("button", { name: "Casual" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Warmth 2 — Mild" })).toHaveAttribute("aria-pressed", "true");
  });

  it("shows the empty state (not an error) when no garment is found", async () => {
    mockedPost.mockResolvedValueOnce({
      data: {
        photo_path: "user-a/x.jpg",
        extraction_ok: false,
        extracted: {},
        color_names: [],
      },
      error: undefined,
      response: new Response(),
    });

    render(<AddItemFlow onClose={vi.fn()} />);
    await selectFile();

    expect(await screen.findByText(/I couldn't find any clothing in that photo/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retake photo" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enter manually" })).toBeInTheDocument();
  });

  it("Enter manually advances to the same blank review card", async () => {
    mockedPost.mockResolvedValueOnce({
      data: { photo_path: "user-a/x.jpg", extraction_ok: false, extracted: {}, color_names: [] },
      error: undefined,
      response: new Response(),
    });

    render(<AddItemFlow onClose={vi.fn()} />);
    await selectFile();
    await userEvent.click(await screen.findByRole("button", { name: "Enter manually" }));

    expect(screen.getByLabelText("Name")).toHaveValue("");
    expect(screen.queryByLabelText("Color 1")).not.toBeInTheDocument();
  });

  it("shows the distinct error state on a genuine extract failure", async () => {
    mockedPost.mockResolvedValueOnce({ data: undefined, error: { detail: "boom" }, response: new Response() });

    render(<AddItemFlow onClose={vi.fn()} />);
    await selectFile();

    expect(await screen.findByText("That upload didn't go through.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("saves and closes the overlay on successful save", async () => {
    mockedPost
      .mockResolvedValueOnce({
        data: {
          photo_path: "user-a/x.jpg",
          extraction_ok: true,
          extracted: {
            category: "top",
            colors: ["#1b2a4a"],
            formality: "casual",
            warmth: 2,
            season: ["spring"],
            background_color: "#e8e2d5",
          },
          color_names: ["navy"],
        },
        error: undefined,
        response: new Response(),
      })
      .mockResolvedValueOnce({ data: { id: "new-item" }, error: undefined, response: new Response() });

    const onClose = vi.fn();
    render(<AddItemFlow onClose={onClose} />);
    await selectFile();
    await screen.findByRole("button", { name: "Top" });
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));

    expect(onClose).toHaveBeenCalled();
    expect(mockedPost).toHaveBeenCalledWith(
      "/api/v1/closet/items/from-upload",
      // Hex, and every detected attribute — not the six-field subset that
      // used to drop formality/warmth/season/pattern/fit (design-decisions §30).
      expect.objectContaining({
        body: expect.objectContaining({
          colors: ["#1b2a4a"],
          formality: "casual",
          warmth: 2,
          season: ["spring"],
          // The photo's backdrop, detected but never shown — it letterboxes
          // a non-square photo to 1:1. Was extracted and stored in the
          // database, then not threaded to the request for one commit, so
          // every item saved through the UI got null (design-decisions §31).
          photo_background_color: "#e8e2d5",
        }),
      })
    );
  });
});
