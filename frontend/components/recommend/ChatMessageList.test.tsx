import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatMessageList, type ChatMessage } from "./ChatMessageList";

const outfit = {
  rationale_text: "",
  items: [
    { id: "item-1", name: "Navy tee", category: "t-shirt", category_group: "top" as const, colors: [], color_names: [], photo_url: null },
  ],
  match_label: "great" as const,
};

const citations = [{ number: 1, text: "Casual denim pairs with a relaxed top." }];

describe("ChatMessageList", () => {
  it("renders user messages right-aligned", () => {
    const messages: ChatMessage[] = [{ id: "1", role: "user", text: "business casual" }];
    render(<ChatMessageList messages={messages} inFlight={false} />);
    expect(screen.getByText("business casual")).toBeInTheDocument();
  });

  it("parses [n] tokens into citation badges", () => {
    const messages: ChatMessage[] = [
      { id: "1", role: "assistant", text: "A relaxed top pairs well here.[1]" },
    ];
    render(<ChatMessageList messages={messages} inFlight={false} />);
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText(/A relaxed top pairs well here\./)).toBeInTheDocument();
  });

  it("renders the thumbnail row and rule list count matching citations", () => {
    const messages: ChatMessage[] = [
      { id: "1", role: "assistant", text: "Reply text.[1]", outfit, citations },
    ];
    render(<ChatMessageList messages={messages} inFlight={false} />);
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(screen.getByText("Casual denim pairs with a relaxed top.")).toBeInTheDocument();
  });

  it("shows a Thinking… row while in flight", () => {
    render(<ChatMessageList messages={[]} inFlight={true} />);
    expect(screen.getByText("Thinking…")).toBeInTheDocument();
  });

  it("hides the Thinking… row when not in flight", () => {
    render(<ChatMessageList messages={[]} inFlight={false} />);
    expect(screen.queryByText("Thinking…")).not.toBeInTheDocument();
  });
});
