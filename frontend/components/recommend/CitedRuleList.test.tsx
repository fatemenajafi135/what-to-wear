import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CitedRuleList } from "./CitedRuleList";

describe("CitedRuleList", () => {
  it("renders one row per citation, numbered", () => {
    const citations = [
      { number: 1, text: "First rule explained." },
      { number: 2, text: "Second rule explained." },
    ];
    render(<CitedRuleList citations={citations} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("First rule explained.")).toBeInTheDocument();
    expect(screen.getByText("Second rule explained.")).toBeInTheDocument();
  });

  it("renders nothing for zero citations", () => {
    const { container } = render(<CitedRuleList citations={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
