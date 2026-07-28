import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Banner } from "./Banner";

describe("Banner", () => {
  it.each(["offline", "error", "info"] as const)("renders the %s variant with role=status", (variant) => {
    render(<Banner variant={variant}>Some message</Banner>);
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent("Some message");
  });

  it("renders an optional trailing action", async () => {
    const onClick = vi.fn();
    render(
      <Banner variant="info" action={{ label: "Retry", onClick }}>
        Something went wrong.
      </Banner>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("renders plain text with no action when none is provided", () => {
    render(<Banner variant="offline">You're offline.</Banner>);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
