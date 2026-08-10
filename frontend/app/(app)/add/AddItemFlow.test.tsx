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

const FULL_REGION = { x: 0, y: 0, width: 1, height: 1 };

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

/** One photo, one detection — feature 018 still wraps this in `drafts`. */
function draft(overrides: { extraction_ok?: boolean; category?: string | null } = {}) {
  const { extraction_ok = true, category = "top" } = overrides;
  return {
    photo_path: "user-a/x.jpg",
    extraction_ok,
    extracted: extraction_ok
      ? {
          category,
          colors: ["#1b2a4a"],
          fabric: "cotton",
          formality: "casual",
          warmth: 2,
          season: ["spring"],
          pattern: "solid",
          fit: "regular",
        }
      : {},
    region: FULL_REGION,
    isolated_photo_path: null,
    isolated_photo_url: null,
    color_names: extraction_ok ? ["navy"] : [],
  };
}

describe("AddItemFlow", () => {
  it("shows the review card pre-filled after a successful scan", async () => {
    mockedPost.mockResolvedValueOnce({
      data: { drafts: [draft()], truncated: false },
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

  it("shows the uploaded photo while scanning, not just plain text (issue #31)", async () => {
    let resolvePost!: (value: unknown) => void;
    mockedPost.mockReturnValueOnce(
      new Promise((resolve) => {
        resolvePost = resolve;
      }) as never
    );

    render(<AddItemFlow onClose={vi.fn()} />);
    await selectFile();

    expect(await screen.findByText("Scanning…")).toBeInTheDocument();
    const photo = document.querySelector("img");
    expect(photo).toHaveAttribute("src", "blob:fake-url");

    resolvePost({
      data: { drafts: [draft({ extraction_ok: false, category: null })], truncated: false },
      error: undefined,
      response: new Response(),
    });
  });

  it("shows the empty state (not an error) when no garment is found", async () => {
    mockedPost.mockResolvedValueOnce({
      data: { drafts: [draft({ extraction_ok: false, category: null })], truncated: false },
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
      data: { drafts: [draft({ extraction_ok: false, category: null })], truncated: false },
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

  it("shows the distinct error state when the response has no drafts at all", async () => {
    mockedPost.mockResolvedValueOnce({
      data: { drafts: [], truncated: false },
      error: undefined,
      response: new Response(),
    });

    render(<AddItemFlow onClose={vi.fn()} />);
    await selectFile();

    expect(await screen.findByText("That upload didn't go through.")).toBeInTheDocument();
  });

  it("saves and closes the overlay on successful save", async () => {
    mockedPost
      .mockResolvedValueOnce({
        data: {
          drafts: [
            {
              ...draft(),
              extracted: { ...draft().extracted, background_color: "#e8e2d5" },
            },
          ],
          truncated: false,
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
          // Feature 018: found missing in /speckit-analyze (finding C1) —
          // every backend/display piece for isolated images worked, but
          // nothing sent the path back on save.
          isolated_photo_path: null,
        }),
      })
    );
  });

  describe("one photo, several detected garments (feature 018, spec.md FR-001/FR-025)", () => {
    function twoDrafts(truncated = false) {
      return {
        data: {
          drafts: [
            { ...draft({ category: "t-shirt" }), region: { x: 0, y: 0, width: 0.4, height: 0.6 } },
            { ...draft({ category: "jeans" }), region: { x: 0.5, y: 0, width: 0.4, height: 0.6 } },
          ],
          truncated,
        },
        error: undefined,
        response: new Response(),
      };
    }

    it("reviews each detection as its own card, in place, without a second screen", async () => {
      mockedPost.mockResolvedValueOnce(twoDrafts());

      render(<AddItemFlow onClose={vi.fn()} />);
      await selectFile();

      expect(await screen.findByRole("button", { name: "T-shirt" })).toHaveAttribute("aria-pressed", "true");
      expect(screen.getByRole("button", { name: "Save & next" })).toBeInTheDocument();
    });

    it("Save & next advances to the second detection's card", async () => {
      mockedPost
        .mockResolvedValueOnce(twoDrafts())
        .mockResolvedValueOnce({ data: { id: "item-1" }, error: undefined, response: new Response() });

      render(<AddItemFlow onClose={vi.fn()} />);
      await selectFile();
      await screen.findByRole("button", { name: "T-shirt" });
      await userEvent.click(screen.getByRole("button", { name: "Save & next" }));

      expect(await screen.findByRole("button", { name: "Jeans" })).toHaveAttribute("aria-pressed", "true");
      expect(screen.getByRole("button", { name: "Save to Closet" })).toBeInTheDocument();
    });

    it("shows the detection-cap notice only on the last card", async () => {
      mockedPost.mockResolvedValueOnce(twoDrafts(true));

      render(<AddItemFlow onClose={vi.fn()} />);
      await selectFile();
      await screen.findByRole("button", { name: "T-shirt" });

      expect(screen.queryByText(/could only add/)).not.toBeInTheDocument();
    });

    it("reports its position once there's more than one detection to review", async () => {
      mockedPost.mockResolvedValueOnce(twoDrafts());
      const onPositionChange = vi.fn();

      render(<AddItemFlow onClose={vi.fn()} onPositionChange={onPositionChange} />);
      await selectFile();
      await screen.findByRole("button", { name: "T-shirt" });

      expect(onPositionChange).toHaveBeenLastCalledWith({ current: 1, total: 2 });
    });

    it("never reports a position for the ordinary single-detection case", async () => {
      mockedPost.mockResolvedValueOnce({ data: { drafts: [draft()], truncated: false }, error: undefined, response: new Response() });
      const onPositionChange = vi.fn();

      render(<AddItemFlow onClose={vi.fn()} onPositionChange={onPositionChange} />);
      await selectFile();
      await screen.findByRole("button", { name: "Top" });

      expect(onPositionChange).toHaveBeenLastCalledWith(null);
    });
  });
});
