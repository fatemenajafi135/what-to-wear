import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import { BulkQueue } from "./BulkQueue";

vi.mock("@/lib/api/client", () => ({
  apiClient: { POST: vi.fn() },
}));

const mockedPost = vi.mocked(apiClient.POST);

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
      },
      color_names: ["navy"],
    },
    error: undefined,
    response: new Response(),
  };
}

beforeEach(() => {
  mockedPost.mockReset();
  URL.createObjectURL = vi.fn(() => "blob:fake-url");
});

function makeFiles(n: number): File[] {
  return Array.from({ length: n }, (_, i) => new File(["fake"], `photo-${i}.jpg`, { type: "image/jpeg" }));
}

describe("BulkQueue", () => {
  it("scans every photo upfront and shows the first card with an announced position", async () => {
    mockedPost
      .mockResolvedValueOnce(extractResponse("user-a/0.jpg", "top"))
      .mockResolvedValueOnce(extractResponse("user-a/1.jpg", "bottom"))
      .mockResolvedValueOnce(extractResponse("user-a/2.jpg", "footwear"));

    render(<BulkQueue files={makeFiles(3)} onClose={vi.fn()} />);

    expect(await screen.findByText("Reviewing item 1 of 3")).toBeInTheDocument();
    expect(screen.getByLabelText("Group")).toHaveValue("top");
    await waitFor(() => expect(mockedPost).toHaveBeenCalledTimes(3));
  });

  it("Save & next advances to the next card and announces the updated position", async () => {
    mockedPost
      .mockResolvedValueOnce(extractResponse("user-a/0.jpg", "top"))
      .mockResolvedValueOnce(extractResponse("user-a/1.jpg", "bottom"))
      .mockResolvedValueOnce({ data: { id: "item-1" }, error: undefined, response: new Response() });

    render(<BulkQueue files={makeFiles(2)} onClose={vi.fn()} />);
    await screen.findByText("Reviewing item 1 of 2");
    await userEvent.click(screen.getByRole("button", { name: "Save & next" }));

    expect(await screen.findByText("Reviewing item 2 of 2")).toBeInTheDocument();
    expect(screen.getByLabelText("Group")).toHaveValue("bottom");
  });

  it("isolates a failed card: it shows Try again, already-saved cards stay saved, queue does not advance", async () => {
    mockedPost
      .mockResolvedValueOnce(extractResponse("user-a/0.jpg", "top"))
      .mockResolvedValueOnce(extractResponse("user-a/1.jpg", "bottom"))
      .mockResolvedValueOnce({ data: { id: "item-1" }, error: undefined, response: new Response() }) // save card 1: success
      .mockResolvedValueOnce({ data: undefined, error: { detail: "boom" }, response: new Response() }); // save card 2: fails

    render(<BulkQueue files={makeFiles(2)} onClose={vi.fn()} />);
    await screen.findByText("Reviewing item 1 of 2");
    await userEvent.click(screen.getByRole("button", { name: "Save & next" }));

    await screen.findByText("Reviewing item 2 of 2");
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));

    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
    // Still on card 2 — the queue did not silently skip past the failure.
    expect(screen.getByText("Reviewing item 2 of 2")).toBeInTheDocument();
  });

  it("finishes and closes the overlay when the last card saves successfully", async () => {
    mockedPost
      .mockResolvedValueOnce(extractResponse("user-a/0.jpg", "top"))
      .mockResolvedValueOnce({ data: { id: "item-1" }, error: undefined, response: new Response() });

    const onClose = vi.fn();
    render(<BulkQueue files={makeFiles(1)} onClose={onClose} />);
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

      render(<BulkQueue files={makeFiles(1)} onClose={vi.fn()} />);

      expect(await screen.findByText("That upload didn't go through.")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
      // The unsaveable card is never offered as a review form at all.
      expect(screen.queryByRole("button", { name: "Save to Closet" })).not.toBeInTheDocument();
    });

    it("retries just that photo and recovers into a normal review card", async () => {
      mockedPost
        .mockResolvedValueOnce({ data: undefined, error: { detail: "nope" }, response: new Response() })
        .mockResolvedValueOnce(extractResponse("user-a/0.jpg", "top"));

      render(<BulkQueue files={makeFiles(1)} onClose={vi.fn()} />);
      await userEvent.click(await screen.findByRole("button", { name: "Try again" }));

      expect(await screen.findByRole("button", { name: "Save to Closet" })).toBeInTheDocument();
      expect(screen.getByLabelText("Group")).toHaveValue("top");
    });

    it("can be skipped so one bad photo doesn't strand the rest of the batch", async () => {
      mockedPost
        .mockResolvedValueOnce({ data: undefined, error: { detail: "nope" }, response: new Response() })
        .mockResolvedValueOnce(extractResponse("user-a/1.jpg", "bottom"));

      render(<BulkQueue files={makeFiles(2)} onClose={vi.fn()} />);
      await userEvent.click(await screen.findByRole("button", { name: "Skip this photo" }));

      expect(await screen.findByText("Reviewing item 2 of 2")).toBeInTheDocument();
      expect(screen.getByLabelText("Group")).toHaveValue("bottom");
    });

    it("closes the overlay when the only failing photo is also the last one", async () => {
      mockedPost.mockResolvedValueOnce({ data: undefined, error: { detail: "nope" }, response: new Response() });

      const onClose = vi.fn();
      render(<BulkQueue files={makeFiles(1)} onClose={onClose} />);
      await userEvent.click(await screen.findByRole("button", { name: "Skip and finish" }));

      await waitFor(() => expect(onClose).toHaveBeenCalled());
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

    render(<BulkQueue files={makeFiles(1)} onClose={vi.fn()} />);

    expect(await screen.findByRole("button", { name: "Save to Closet" })).toBeInTheDocument();
    expect(screen.queryByText("That upload didn't go through.")).not.toBeInTheDocument();
  });
});
