import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { components } from "@/lib/api/schema";
import { SessionMessages } from "./SessionMessages";

type SessionMessageView = components["schemas"]["SessionMessageView"];

describe("SessionMessages", () => {
  it("renders a user message as a plain-text user bubble", () => {
    const messages: SessionMessageView[] = [
      { id: "m1", kind: "user_message", role: "user", text: "Something for a rainy commute", outfits: [] },
    ];
    render(<SessionMessages messages={messages} />);
    expect(screen.getByText("Something for a rainy commute")).toBeInTheDocument();
  });

  it("renders a zero-outfit styling_reply as plain assistant text with no citation badge", () => {
    const messages: SessionMessageView[] = [
      {
        id: "m2",
        kind: "styling_reply",
        role: "assistant",
        text: "I couldn't put an outfit together from that.",
        outfits: [],
      },
    ];
    render(<SessionMessages messages={messages} />);
    expect(screen.getByText("I couldn't put an outfit together from that.")).toBeInTheDocument();
    expect(screen.queryByText(/^\d+$/)).not.toBeInTheDocument();
  });

  it("renders an outfit-bearing styling_reply with citation badges, no thumbnails, no rule list", () => {
    const messages: SessionMessageView[] = [
      {
        id: "m3",
        kind: "styling_reply",
        role: "assistant",
        text: "",
        outfits: [
          {
            id: "outfit-1",
            title: "Rainy day commute",
            rationale_with_citations: "A cohesive, weather-ready look. [1]",
            citations: [{ number: 1, text: "Pair casual denim with a relaxed top." }],
          },
        ],
      },
    ];
    const { container } = render(<SessionMessages messages={messages} />);

    expect(screen.getByText("1")).toBeInTheDocument(); // the citation badge
    expect(screen.getByText(/A cohesive, weather-ready look\./)).toBeInTheDocument();

    // No item-thumbnail rows and no rule list anywhere on this surface
    // (docs/design-decisions.md §46 — deliberate asymmetry with Outfit detail).
    expect(container.querySelector("img")).not.toBeInTheDocument();
    expect(screen.queryByText("Pair casual denim with a relaxed top.")).not.toBeInTheDocument();
  });

  it("renders messages in the order given", () => {
    const messages: SessionMessageView[] = [
      { id: "m1", kind: "user_message", role: "user", text: "First", outfits: [] },
      { id: "m2", kind: "styling_reply", role: "assistant", text: "Second", outfits: [] },
    ];
    render(<SessionMessages messages={messages} />);
    const rendered = screen.getAllByText(/First|Second/);
    expect(rendered.map((el) => el.textContent)).toEqual(["First", "Second"]);
  });
});
