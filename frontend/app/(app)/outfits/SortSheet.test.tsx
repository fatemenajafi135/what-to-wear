import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SortSheet, SortSheetTrigger } from "./SortSheet";

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  });
});

describe("SortSheetTrigger", () => {
  it("calls onOpen when clicked", async () => {
    const onOpen = vi.fn();
    render(<SortSheetTrigger onOpen={onOpen} />);
    await userEvent.click(screen.getByText("Filter & sort"));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});

describe("SortSheet", () => {
  it("renders the three sort options, no filter facets", () => {
    render(<SortSheet open onClose={vi.fn()} sort="date" onChange={vi.fn()} />);
    expect(screen.getByText(/Date added/)).toBeInTheDocument();
    expect(screen.getByText("Favorited first")).toBeInTheDocument();
    expect(screen.getByText("Most worn")).toBeInTheDocument();
    // Deferred per design-decisions.md §41 — no filter facets ship here.
    expect(screen.queryByText(/occasion/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/weather/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/formality/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Clear")).not.toBeInTheDocument();
  });

  it("marks the active sort as current", () => {
    render(<SortSheet open onClose={vi.fn()} sort="most_worn" onChange={vi.fn()} />);
    expect(screen.getByText("Most worn (current)")).toBeInTheDocument();
  });

  it("closes then calls onChange with the selected sort", async () => {
    const onClose = vi.fn();
    const onChange = vi.fn();
    render(<SortSheet open onClose={onClose} sort="date" onChange={onChange} />);
    await userEvent.click(screen.getByText("Favorited first"));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("favorite");
  });
});
