import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatMessageList, type ChatMessage } from "./ChatMessageList";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));

const outfit = {
  id: "outfit-1",
  favorite: true,
  occasion: "business casual",
  rationale_text: "A relaxed top pairs well here.",
  items: [
    {
      id: "item-1",
      name: "Navy tee",
      category: "t-shirt",
      category_group: "top" as const,
      colors: [],
      color_names: [],
      photo_url: null,
      photo_background_color: null,
    },
  ],
  match_label: "great" as const,
  meta_line: "business casual · Business casual",
};

beforeEach(() => {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
});

describe("ChatMessageList", () => {
  it("renders user messages right-aligned", () => {
    const messages: ChatMessage[] = [{ id: "1", role: "user", text: "business casual" }];
    render(<ChatMessageList messages={messages} turnPending={false} stylingPending={false} />);
    expect(screen.getByText("business casual")).toBeInTheDocument();
  });

  it("renders an outfit reply as a pager card with no citation markers", () => {
    const messages: ChatMessage[] = [{ id: "1", role: "assistant", outfits: [outfit] }];
    render(<ChatMessageList messages={messages} turnPending={false} stylingPending={false} />);
    expect(screen.getByText(/A relaxed top pairs well here\./)).toBeInTheDocument();
    expect(screen.queryByText(/\[\d+]/)).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Navy tee" })).toHaveLength(1);
  });

  it("renders the Empty message plus an Add-item link when a Start-styling reply has zero outfits", () => {
    const messages: ChatMessage[] = [
      { id: "1", role: "assistant", outfits: [], replyText: "I couldn't put an outfit together from that." },
    ];
    render(<ChatMessageList messages={messages} turnPending={false} stylingPending={false} />);
    expect(screen.getByText("I couldn't put an outfit together from that.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add items to your closet" })).toHaveAttribute("href", "/add");
  });

  it("renders a plain conversational reply with no Add-item link", () => {
    const messages: ChatMessage[] = [{ id: "1", role: "assistant", replyText: "Got it.", plain: true }];
    render(<ChatMessageList messages={messages} turnPending={false} stylingPending={false} />);
    expect(screen.getByText("Got it.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Add items to your closet" })).not.toBeInTheDocument();
  });

  it("shows the pager's skeleton card while a Start-styling request is pending", () => {
    render(<ChatMessageList messages={[]} turnPending={false} stylingPending={true} />);
    expect(screen.getByRole("status", { name: "Styling your outfit…" })).toBeInTheDocument();
  });

  it("hides the skeleton card when nothing is pending", () => {
    render(<ChatMessageList messages={[]} turnPending={false} stylingPending={false} />);
    expect(screen.queryByRole("status", { name: "Styling your outfit…" })).not.toBeInTheDocument();
  });

  it("shows the Thinking… bubble while a conversational turn is pending", () => {
    render(<ChatMessageList messages={[]} turnPending={true} stylingPending={false} />);
    expect(screen.getByText("Thinking…")).toBeInTheDocument();
  });

  it("hides the Thinking… bubble once the turn is no longer pending", () => {
    render(<ChatMessageList messages={[]} turnPending={false} stylingPending={false} />);
    expect(screen.queryByText("Thinking…")).not.toBeInTheDocument();
  });

  it("shows both bubbles independently — turnPending and stylingPending never overlap in practice, but rendering must not assume that", () => {
    render(<ChatMessageList messages={[]} turnPending={true} stylingPending={true} />);
    expect(screen.getByText("Thinking…")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Styling your outfit…" })).toBeInTheDocument();
  });
});
