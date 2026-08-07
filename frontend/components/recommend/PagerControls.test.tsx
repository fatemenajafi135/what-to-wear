import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PagerControls } from "./PagerControls";

describe("PagerControls", () => {
  it("renders nothing at count 1", () => {
    const { container } = render(<PagerControls index={0} count={1} onPrev={vi.fn()} onNext={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the indicator and both arrows at count > 1", () => {
    render(<PagerControls index={1} count={4} onPrev={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByText("2 of 4")).toBeInTheDocument();
    expect(screen.getByLabelText("Previous suggestion")).toBeEnabled();
    expect(screen.getByLabelText("Next suggestion")).toBeEnabled();
  });

  it("disables Previous at the first card", () => {
    render(<PagerControls index={0} count={3} onPrev={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByLabelText("Previous suggestion")).toBeDisabled();
    expect(screen.getByLabelText("Next suggestion")).toBeEnabled();
  });

  it("disables Next at the last card", () => {
    render(<PagerControls index={2} count={3} onPrev={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByLabelText("Next suggestion")).toBeDisabled();
    expect(screen.getByLabelText("Previous suggestion")).toBeEnabled();
  });

  it("calls onPrev/onNext on click", async () => {
    const user = userEvent.setup();
    const onPrev = vi.fn();
    const onNext = vi.fn();
    render(<PagerControls index={1} count={3} onPrev={onPrev} onNext={onNext} />);

    await user.click(screen.getByLabelText("Previous suggestion"));
    await user.click(screen.getByLabelText("Next suggestion"));

    expect(onPrev).toHaveBeenCalledTimes(1);
    expect(onNext).toHaveBeenCalledTimes(1);
  });
});
