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
      extracted: { category, colors: ["#1b2a4a"] },
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
});
