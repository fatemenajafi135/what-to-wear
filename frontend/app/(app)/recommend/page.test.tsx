import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import RecommendPage from "./page";

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    GET: vi.fn((url: string) =>
      url === "/api/v1/recommend/readiness"
        ? Promise.resolve({ data: { ready: true, sparse: false, missing: [] } })
        : Promise.resolve({ data: { picked: false, event: null } }),
    ),
    POST: vi.fn(),
  },
}));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { getSession: () => Promise.resolve({ data: { session: null } }) } }),
}));

import { apiClient } from "@/lib/api/client";

describe("RecommendPage", () => {
  it("renders the TopHeader title and subtitle", () => {
    render(<RecommendPage />);
    expect(screen.getByRole("heading", { name: "Styling" })).toBeInTheDocument();
    expect(screen.getByText("Ask for an outfit, get cited picks from your closet")).toBeInTheDocument();
  });

  it("renders the hero state on first load", async () => {
    render(<RecommendPage />);
    expect(await screen.findByText("What to Wear")).toBeInTheDocument();
    expect(screen.getByText("Rainy day commute")).toBeInTheDocument();
  });

  it("New chat is disabled on a fresh (empty) thread", async () => {
    render(<RecommendPage />);
    await screen.findByLabelText("Message");
    expect(screen.getByLabelText("New chat")).toBeDisabled();
  });

  it("New chat becomes enabled after a message is sent, and resets the thread on click", async () => {
    vi.mocked(apiClient.POST).mockResolvedValue({
      data: {
        thread_id: "thread-1",
        reply_text: null,
        outfit: {
          rationale_text: "Reply.",
          items: [],
          match_label: "great",
        },
        citations: [],
      },
      error: undefined,
      response: new Response(),
    } as never);

    render(<RecommendPage />);
    await userEvent.type(await screen.findByLabelText("Message"), "business casual{Enter}");
    expect(screen.getByLabelText("New chat")).toBeEnabled();

    await userEvent.click(screen.getByText("Start styling"));
    await waitFor(() => expect(screen.getByText("Reply.")).toBeInTheDocument());

    await userEvent.click(screen.getByLabelText("New chat"));

    expect(screen.getByText("What to Wear")).toBeInTheDocument();
    expect(screen.getByLabelText("New chat")).toBeDisabled();
  });

  it("Chat history is present but inert (no /history route exists yet)", async () => {
    render(<RecommendPage />);
    await screen.findByLabelText("Message");
    expect(screen.getByLabelText("Chat history")).toBeDisabled();
  });
});
