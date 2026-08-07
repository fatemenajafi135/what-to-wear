import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "./Badge";

describe("Badge", () => {
  it.each(["citation", "status", "muted", "count"] as const)("renders the %s tone", (tone) => {
    render(<Badge tone={tone}>1</Badge>);
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("renders as a non-interactive span, not a button or link", () => {
    render(<Badge tone="status">Connected</Badge>);
    const el = screen.getByText("Connected");
    expect(el.tagName).toBe("SPAN");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
