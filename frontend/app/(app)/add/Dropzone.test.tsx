import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Dropzone } from "./Dropzone";
import { isCameraPrimed } from "@/lib/camera/primed";

vi.mock("@/lib/useOnlineStatus", () => ({ useOnlineStatus: vi.fn(() => true) }));
vi.mock("@/lib/camera/primed", () => ({
  isCameraPrimed: vi.fn(() => false),
  setCameraPrimed: vi.fn(),
}));

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("Dropzone", () => {
  it("shows the upload placeholder copy", () => {
    render(<Dropzone onFileSelected={vi.fn()} />);
    expect(screen.getByText("tap to upload photo (garment scan)")).toBeInTheDocument();
  });

  it("shows the camera primer on first tap when not yet primed", async () => {
    render(<Dropzone onFileSelected={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /tap to upload photo/ }));
    expect(screen.getByRole("heading", { name: "Before you scan" })).toBeInTheDocument();
  });

  it("does not show the primer when already primed", async () => {
    vi.mocked(isCameraPrimed).mockReturnValue(true);
    render(<Dropzone onFileSelected={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /tap to upload photo/ }));
    expect(screen.queryByRole("heading", { name: "Before you scan" })).not.toBeInTheDocument();
  });

  it("is disabled when offline", async () => {
    const { useOnlineStatus } = await import("@/lib/useOnlineStatus");
    vi.mocked(useOnlineStatus).mockReturnValue(false);
    render(<Dropzone onFileSelected={vi.fn()} />);
    expect(screen.getByRole("button", { name: /tap to upload photo/ })).toBeDisabled();
  });

  it("calls onFileSelected when a file is chosen", async () => {
    const onFileSelected = vi.fn();
    const { container } = render(<Dropzone onFileSelected={onFileSelected} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["fake"], "shirt.jpg", { type: "image/jpeg" });
    await userEvent.upload(input, file);
    expect(onFileSelected).toHaveBeenCalledWith(file);
  });
});
