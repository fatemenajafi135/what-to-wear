import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import AddItemPage from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
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
});
