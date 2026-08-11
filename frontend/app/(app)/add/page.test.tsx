import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import AddItemPage from "./page";

// Hoisted + stable across renders: the real useRouter's return value is
// stable too, and issue #62's tests below need to assert on the same
// back/push spies the component actually called, not a fresh pair minted
// on every render.
const { back, push } = vi.hoisted(() => ({ back: vi.fn(), push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ back, push }),
}));
vi.mock("@/lib/api/client", () => ({
  apiClient: { POST: vi.fn() },
}));
vi.mock("@/lib/useOnlineStatus", () => ({ useOnlineStatus: vi.fn(() => true) }));
vi.mock("@/lib/camera/primed", () => ({
  isCameraPrimed: vi.fn(() => true),
  setCameraPrimed: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(apiClient.POST).mockReset();
  back.mockClear();
  push.mockClear();
  // jsdom defaults history.length to 1; /add is always reached via in-app
  // navigation in practice (docs/design-decisions.md §9), so tests below
  // that assert on the close button's back() path set this explicitly.
  Object.defineProperty(window.history, "length", { value: 2, configurable: true });
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  });
  URL.createObjectURL = vi.fn(() => "blob:fake-url");
});

describe("AddItemPage", () => {
  it("opens on the Add to Closet choice sheet", () => {
    render(<AddItemPage />);
    expect(screen.getByRole("heading", { name: "Add to Closet" })).toBeInTheDocument();
  });

  it("choosing single item shows the Dropzone", async () => {
    render(<AddItemPage />);
    await userEvent.click(screen.getByText("Add one item"));
    expect(screen.getByText("tap to upload photo (garment scan)")).toBeInTheDocument();
  });

  it("choosing bulk items and selecting files shows the BulkQueue", async () => {
    vi.mocked(apiClient.POST).mockResolvedValue({
      data: { photo_path: "user-a/0.jpg", extraction_ok: true, extracted: { category: "top" }, color_names: [] },
      error: undefined,
      response: new Response(),
    });

    const { container } = render(<AddItemPage />);
    await userEvent.click(screen.getByText("Add bulk items"));

    const bulkInput = container.querySelector('input[type="file"][multiple]') as HTMLInputElement;
    const file = new File(["fake"], "shirt.jpg", { type: "image/jpeg" });
    await userEvent.upload(bulkInput, file);

    expect(await screen.findByText("Reviewing item 1 of 1")).toBeInTheDocument();
  });

  it("selecting more than 10 files truncates the bulk queue to 10 (issue #61)", async () => {
    vi.mocked(apiClient.POST).mockResolvedValue({
      data: { photo_path: "user-a/0.jpg", extraction_ok: true, extracted: { category: "top" }, color_names: [] },
      error: undefined,
      response: new Response(),
    });

    const { container } = render(<AddItemPage />);
    await userEvent.click(screen.getByText("Add bulk items"));

    const bulkInput = container.querySelector('input[type="file"][multiple]') as HTMLInputElement;
    const files = Array.from({ length: 15 }, (_, i) => new File(["fake"], `item-${i}.jpg`, { type: "image/jpeg" }));
    await userEvent.upload(bulkInput, files);

    expect(await screen.findByText("Reviewing item 1 of 10")).toBeInTheDocument();
  });

  // issue #62 / docs/design-decisions.md §64: the risk the issue names —
  // closing mid-batch after some items already saved, with zero warning.
  describe("closing mid-bulk-batch", () => {
    // ReviewCard's own validation (colors/formality/warmth/season) rejects
    // a Save with any of those blank, so — unlike the truncation test above,
    // which never submits — this needs a fully-filled scan response, not
    // just a category.
    function extractResponse(category: string) {
      return {
        data: {
          photo_path: "user-a/0.jpg",
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

    it("closes immediately, no confirmation, while nothing in the batch has saved yet", async () => {
      vi.mocked(apiClient.POST).mockResolvedValue(extractResponse("top"));

      const { container } = render(<AddItemPage />);
      await userEvent.click(screen.getByText("Add bulk items"));
      const bulkInput = container.querySelector('input[type="file"][multiple]') as HTMLInputElement;
      await userEvent.upload(bulkInput, [new File(["fake"], "a.jpg", { type: "image/jpeg" })]);
      await screen.findByText("Reviewing item 1 of 1");

      await userEvent.click(screen.getByRole("button", { name: "Close" }));

      expect(screen.queryByRole("heading", { name: "Cancel this batch?" })).not.toBeInTheDocument();
      expect(back).toHaveBeenCalledTimes(1);
    });

    it("asks for confirmation once an item has saved, and cancelling the batch leaves earlier saves alone", async () => {
      vi.mocked(apiClient.POST)
        .mockResolvedValueOnce(extractResponse("top")) // extract 1
        .mockResolvedValueOnce(extractResponse("bottom")) // extract 2
        .mockResolvedValueOnce(extractResponse("footwear")) // extract 3
        .mockResolvedValueOnce({ data: { id: "item-1" }, error: undefined, response: new Response() }); // save card 1

      const { container } = render(<AddItemPage />);
      await userEvent.click(screen.getByText("Add bulk items"));
      const bulkInput = container.querySelector('input[type="file"][multiple]') as HTMLInputElement;
      await userEvent.upload(
        bulkInput,
        Array.from({ length: 3 }, (_, i) => new File(["fake"], `item-${i}.jpg`, { type: "image/jpeg" }))
      );
      await screen.findByText("Reviewing item 1 of 3");
      await userEvent.click(screen.getByRole("button", { name: "Save & next" }));
      await screen.findByText("Reviewing item 2 of 3");

      // Not yet saved (card 2), so closing now would abandon card 1's real
      // save and cards 2-3's unreviewed photos with no warning at all.
      await userEvent.click(screen.getByRole("button", { name: "Close" }));
      expect(back).not.toHaveBeenCalled();
      expect(
        screen.getByText("1 of 3 items are already saved to your closet. The rest won't be added.")
      ).toBeInTheDocument();

      await userEvent.click(screen.getByRole("button", { name: "Cancel batch" }));

      expect(back).toHaveBeenCalledTimes(1);
      // Exactly 4 calls total: 3 upfront extracts + the 1 save already made
      // for card 1. Cancelling never issues a save for cards 2 or 3, and
      // nothing about card 1's already-saved item is touched again — it
      // just stays saved, per §64.
      expect(apiClient.POST).toHaveBeenCalledTimes(4);
    });

    it("Keep reviewing dismisses the confirmation and leaves the batch in place", async () => {
      vi.mocked(apiClient.POST)
        .mockResolvedValueOnce(extractResponse("top"))
        .mockResolvedValueOnce(extractResponse("bottom"))
        .mockResolvedValueOnce({ data: { id: "item-1" }, error: undefined, response: new Response() });

      const { container } = render(<AddItemPage />);
      await userEvent.click(screen.getByText("Add bulk items"));
      const bulkInput = container.querySelector('input[type="file"][multiple]') as HTMLInputElement;
      await userEvent.upload(
        bulkInput,
        Array.from({ length: 2 }, (_, i) => new File(["fake"], `item-${i}.jpg`, { type: "image/jpeg" }))
      );
      await screen.findByText("Reviewing item 1 of 2");
      await userEvent.click(screen.getByRole("button", { name: "Save & next" }));
      await screen.findByText("Reviewing item 2 of 2");

      await userEvent.click(screen.getByRole("button", { name: "Close" }));
      await userEvent.click(screen.getByRole("button", { name: "Keep reviewing" }));

      expect(back).not.toHaveBeenCalled();
      expect(push).not.toHaveBeenCalled();
      // Still on the batch, card 2, exactly where the confirmation interrupted it.
      expect(screen.getByText("Reviewing item 2 of 2")).toBeInTheDocument();
    });
  });
});
