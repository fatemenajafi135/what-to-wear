import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NoPhoto } from "./NoPhoto";

describe("NoPhoto", () => {
  it("renders a decorative, aria-hidden treatment (not the removed placeholder pattern)", () => {
    const { container } = render(<NoPhoto />);
    const el = container.firstElementChild;
    expect(el).toHaveAttribute("aria-hidden", "true");
  });
});
