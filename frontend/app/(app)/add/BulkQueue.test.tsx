import { useState, type ComponentProps } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import { BulkQueue } from "./BulkQueue";

/**
 * issue #32 moved the "Reviewing item X of Y" indicator out of BulkQueue's
 * own render (into the page's sticky header, via onPositionChange) — this
 * mirrors what page.tsx now does, so the tests below can keep asserting on
 * visible text rather than inspecting callback args directly.
 */
function BulkQueueHarness(props: Omit<ComponentProps<typeof BulkQueue>, "onPositionChange">) {
  const [position, setPosition] = useState<{ current: number; total: number } | null>(null);
  return (
    <>
      {position && <h2>{`Reviewing item ${position.current} of ${position.total}`}</h2>}
      <BulkQueue {...props} onPositionChange={setPosition} />
    </>
  );
}

vi.mock("@/lib/api/client", () => ({
  apiClient: { POST: vi.fn(), GET: vi.fn() },
}));

const mockedPost = vi.mocked(apiClient.POST);
const mockedGet = vi.mocked(apiClient.GET);

function extractResponse(photoPath: string, category: string) {
  return {
    data: {
      photo_path: photoPath,
      extraction_ok: true,
      extracted: {
        category,
        colors: ["#1b2a4a"],
        formality: "casual",
        warmth: 2,
        season: ["spring"],
        fabric: "cotton",
        pattern: "solid",
        fit: "regular",
        background_color: "#e8e2d5",
      },
      color_names: ["navy"],
    },
    error: undefined,
    response: new Response(),
  };
}

beforeEach(() => {
  mockedGet.mockResolvedValue({ data: TAXONOMY, error: undefined, response: new Response() } as never);
  mockedPost.mockReset();
  URL.createObjectURL = vi.fn(() => "blob:fake-url");
});

function makeFiles(n: number): File[] {
  return Array.from({ length: n }, (_, i) => new File(["fake"], `photo-${i}.jpg`, { type: "image/jpeg" }));
}

const TAXONOMY = {
  top: ["blouse", "shirt", "t-shirt"],
  bottom: ["jeans", "trousers"],
  full_body: ["dress"],
  outerwear: ["blazer", "coat"],
  footwear: ["boots", "sneakers"],
  accessory: ["belt", "bow_tie", "necklace", "tie"],
};

describe("BulkQueue", () => {
  it("shows the uploaded photo while scanning, not just plain text (issue #31)", async () => {
    let resolveFirst!: (value: unknown) => void;
    mockedPost.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveFirst = resolve;
      }) as never
    );

    render(<BulkQueueHarness files={makeFiles(1)} onClose={vi.fn()} />);

    expect(await screen.findByText("Scanning…")).toBeInTheDocument();
    const photo = document.querySelector("img");
    expect(photo).toHaveAttribute("src", "blob:fake-url");

    resolveFirst(extractResponse("user-a/0.jpg", "top"));
  });

  it("scans every photo upfront and shows the first card with an announced position", async () => {
    mockedPost
      .mockResolvedValueOnce(extractResponse("user-a/0.jpg", "top"))
      .mockResolvedValueOnce(extractResponse("user-a/1.jpg", "bottom"))
      .mockResolvedValueOnce(extractResponse("user-a/2.jpg", "footwear"));

    render(<BulkQueueHarness files={makeFiles(3)} onClose={vi.fn()} />);

    expect(await screen.findByText("Reviewing item 1 of 3")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Top" })).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => expect(mockedPost).toHaveBeenCalledTimes(3));
  });

  it("Save & next advances to the next card and announces the updated position", async () => {
    mockedPost
      .mockResolvedValueOnce(extractResponse("user-a/0.jpg", "top"))
      .mockResolvedValueOnce(extractResponse("user-a/1.jpg", "bottom"))
      .mockResolvedValueOnce({ data: { id: "item-1" }, error: undefined, response: new Response() });

    render(<BulkQueueHarness files={makeFiles(2)} onClose={vi.fn()} />);
    await screen.findByText("Reviewing item 1 of 2");
    await userEvent.click(screen.getByRole("button", { name: "Save & next" }));

    expect(await screen.findByText("Reviewing item 2 of 2")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Bottom" })).toHaveAttribute("aria-pressed", "true");
  });

  it("isolates a failed card: it shows Try again, already-saved cards stay saved, queue does not advance", async () => {
    mockedPost
      .mockResolvedValueOnce(extractResponse("user-a/0.jpg", "top"))
      .mockResolvedValueOnce(extractResponse("user-a/1.jpg", "bottom"))
      .mockResolvedValueOnce({ data: { id: "item-1" }, error: undefined, response: new Response() }) // save card 1: success
      .mockResolvedValueOnce({ data: undefined, error: { detail: "boom" }, response: new Response() }); // save card 2: fails

    render(<BulkQueueHarness files={makeFiles(2)} onClose={vi.fn()} />);
    await screen.findByText("Reviewing item 1 of 2");
    await userEvent.click(screen.getByRole("button", { name: "Save & next" }));

    await screen.findByText("Reviewing item 2 of 2");
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));

    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
    // Still on card 2 — the queue did not silently skip past the failure.
    expect(screen.getByText("Reviewing item 2 of 2")).toBeInTheDocument();
  });

  // The backdrop the scan read from the photo, never shown to the user — it
  // fills the letterbox when a non-square photo is padded to 1:1. It was
  // added to the extractor and the database and then, for one commit, not
  // threaded into the request body at all.
  it("sends the detected photo background colour", async () => {
    mockedPost
      .mockResolvedValueOnce(extractResponse("user-a/0.jpg", "top"))
      .mockResolvedValueOnce({ data: { id: "item-1" }, error: undefined, response: new Response() });

    render(<BulkQueueHarness files={makeFiles(1)} onClose={vi.fn()} />);
    await screen.findByText("Reviewing item 1 of 1");
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));

    expect(mockedPost).toHaveBeenCalledWith(
      "/api/v1/closet/items/from-upload",
      expect.objectContaining({ body: expect.objectContaining({ photo_background_color: "#e8e2d5" }) })
    );
  });

  it("finishes and closes the overlay when the last card saves successfully", async () => {
    mockedPost
      .mockResolvedValueOnce(extractResponse("user-a/0.jpg", "top"))
      .mockResolvedValueOnce({ data: { id: "item-1" }, error: undefined, response: new Response() });

    const onClose = vi.fn();
    render(<BulkQueueHarness files={makeFiles(1)} onClose={onClose} />);
    await screen.findByText("Reviewing item 1 of 1");
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  // A failed UPLOAD (no photo_path) used to be marked `ready` like any other
  // card, and Save then bailed on a bare `if (!current?.photoPath) return;` —
  // no error, no request, nothing. Every test above mocks a successful
  // extract, which is why the whole class of failure went unnoticed until a
  // real batch produced fifteen extract calls and zero saves.
  describe("a photo whose upload failed", () => {
    it("says so instead of rendering a card whose Save button does nothing", async () => {
      mockedPost.mockResolvedValueOnce({
        data: undefined,
        error: { detail: "storage unreachable" },
        response: new Response(),
      });

      render(<BulkQueueHarness files={makeFiles(1)} onClose={vi.fn()} />);

      expect(await screen.findByText("That upload didn't go through.")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
      // The unsaveable card is never offered as a review form at all.
      expect(screen.queryByRole("button", { name: "Save to Closet" })).not.toBeInTheDocument();
    });

    it("retries just that photo and recovers into a normal review card", async () => {
      mockedPost
        .mockResolvedValueOnce({ data: undefined, error: { detail: "nope" }, response: new Response() })
        .mockResolvedValueOnce(extractResponse("user-a/0.jpg", "top"));

      render(<BulkQueueHarness files={makeFiles(1)} onClose={vi.fn()} />);
      await userEvent.click(await screen.findByRole("button", { name: "Try again" }));

      expect(await screen.findByRole("button", { name: "Save to Closet" })).toBeInTheDocument();
      expect(await screen.findByRole("button", { name: "Top" })).toHaveAttribute("aria-pressed", "true");
    });

    it("can be skipped so one bad photo doesn't strand the rest of the batch", async () => {
      mockedPost
        .mockResolvedValueOnce({ data: undefined, error: { detail: "nope" }, response: new Response() })
        .mockResolvedValueOnce(extractResponse("user-a/1.jpg", "bottom"));

      render(<BulkQueueHarness files={makeFiles(2)} onClose={vi.fn()} />);
      await userEvent.click(await screen.findByRole("button", { name: "Skip this photo" }));

      expect(await screen.findByText("Reviewing item 2 of 2")).toBeInTheDocument();
      expect(await screen.findByRole("button", { name: "Bottom" })).toHaveAttribute("aria-pressed", "true");
    });

    it("closes the overlay when the only failing photo is also the last one", async () => {
      mockedPost.mockResolvedValueOnce({ data: undefined, error: { detail: "nope" }, response: new Response() });

      const onClose = vi.fn();
      render(<BulkQueueHarness files={makeFiles(1)} onClose={onClose} />);
      await userEvent.click(await screen.findByRole("button", { name: "Skip and finish" }));

      await waitFor(() => expect(onClose).toHaveBeenCalled());
    });
  });

  // issue #62: the same skip link the upload-error state already had,
  // generalized to the normal `ready` state — abandoning a photo that
  // scanned fine, not recovering from a failure.
  describe("skipping a normal (ready) card", () => {
    it("advances to the next card without calling the save endpoint", async () => {
      mockedPost
        .mockResolvedValueOnce(extractResponse("user-a/0.jpg", "top"))
        .mockResolvedValueOnce(extractResponse("user-a/1.jpg", "bottom"));

      render(<BulkQueueHarness files={makeFiles(2)} onClose={vi.fn()} />);
      await screen.findByText("Reviewing item 1 of 2");
      await userEvent.click(screen.getByRole("button", { name: "Skip this photo" }));

      expect(await screen.findByText("Reviewing item 2 of 2")).toBeInTheDocument();
      expect(await screen.findByRole("button", { name: "Bottom" })).toHaveAttribute("aria-pressed", "true");
      // Only the two upfront extract calls — never from-upload.
      expect(mockedPost).toHaveBeenCalledTimes(2);
      expect(mockedPost).not.toHaveBeenCalledWith("/api/v1/closet/items/from-upload", expect.anything());
    });

    it("closes the overlay when skipping the last card, without saving it", async () => {
      mockedPost.mockResolvedValueOnce(extractResponse("user-a/0.jpg", "top"));

      const onClose = vi.fn();
      render(<BulkQueueHarness files={makeFiles(1)} onClose={onClose} />);
      await userEvent.click(await screen.findByRole("button", { name: "Skip and finish" }));

      await waitFor(() => expect(onClose).toHaveBeenCalled());
      expect(mockedPost).toHaveBeenCalledTimes(1);
    });

    it("does not skip a saved item — an already-saved card stays saved when a later one is skipped", async () => {
      mockedPost
        .mockResolvedValueOnce(extractResponse("user-a/0.jpg", "top"))
        .mockResolvedValueOnce(extractResponse("user-a/1.jpg", "bottom"))
        .mockResolvedValueOnce({ data: { id: "item-1" }, error: undefined, response: new Response() }); // save card 1

      render(<BulkQueueHarness files={makeFiles(2)} onClose={vi.fn()} />);
      await screen.findByText("Reviewing item 1 of 2");
      await userEvent.click(screen.getByRole("button", { name: "Save & next" }));

      await screen.findByText("Reviewing item 2 of 2");
      await userEvent.click(screen.getByRole("button", { name: "Skip and finish" }));

      // Card 1's save already went through; skipping card 2 never issues a
      // second from-upload call, so nothing about card 1 is touched again.
      expect(mockedPost).toHaveBeenCalledTimes(3);
    });
  });

  // Extraction SUCCEEDING but finding no colour is a different case: the
  // photo did land in Storage, so the card is saveable once the user fills
  // colour in. It must stay a normal review card, not an error.
  it("still offers a saveable card when the scan found no colour", async () => {
    mockedPost.mockResolvedValueOnce({
      data: {
        photo_path: "user-a/0.jpg",
        extraction_ok: true,
        extracted: { category: null, colors: null },
        color_names: [],
      },
      error: undefined,
      response: new Response(),
    });

    render(<BulkQueueHarness files={makeFiles(1)} onClose={vi.fn()} />);

    expect(await screen.findByRole("button", { name: "Save to Closet" })).toBeInTheDocument();
    expect(screen.queryByText("That upload didn't go through.")).not.toBeInTheDocument();
  });
});
