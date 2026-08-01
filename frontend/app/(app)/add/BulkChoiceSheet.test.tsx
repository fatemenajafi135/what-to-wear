import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BulkChoiceSheet } from "./BulkChoiceSheet";

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
  });
});

describe("BulkChoiceSheet", () => {
  it("renders the title, subtitle, and both option rows", () => {
    render(<BulkChoiceSheet open onChooseSingle={vi.fn()} onChooseBulk={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Add to Closet" })).toBeInTheDocument();
    expect(screen.getByText("Choose how you would like to add items.")).toBeInTheDocument();
    expect(screen.getByText("Add bulk items")).toBeInTheDocument();
    expect(screen.getByText("Upload several photos, one item each")).toBeInTheDocument();
  });

  it("calls onChooseSingle when the single-item row is clicked", async () => {
    const onChooseSingle = vi.fn();
    render(<BulkChoiceSheet open onChooseSingle={onChooseSingle} onChooseBulk={vi.fn()} onClose={vi.fn()} />);
    await userEvent.click(screen.getByText("Add one item"));
    expect(onChooseSingle).toHaveBeenCalledTimes(1);
  });

  it("calls onChooseBulk when the bulk row is clicked", async () => {
    const onChooseBulk = vi.fn();
    render(<BulkChoiceSheet open onChooseSingle={vi.fn()} onChooseBulk={onChooseBulk} onClose={vi.fn()} />);
    await userEvent.click(screen.getByText("Add bulk items"));
    expect(onChooseBulk).toHaveBeenCalledTimes(1);
  });
});
