import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import RecommendPage from "./page";
import * as recommendChatStore from "@/lib/recommend/recommendChatStore";

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
let searchParamsValue = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => searchParamsValue,
}));

import { apiClient } from "@/lib/api/client";

function mockGetByUrl(overrides: Record<string, unknown> = {}) {
  return vi.fn((url: string) => {
    if (url in overrides) return Promise.resolve(overrides[url]);
    if (url === "/api/v1/recommend/readiness") {
      return Promise.resolve({ data: { ready: true, sparse: false, missing: [] } });
    }
    if (url === "/api/v1/recommend/sessions/{session_id}") {
      throw new Error("unmocked GET /recommend/sessions/{session_id}");
    }
    return Promise.resolve({ data: { picked: false, event: null } });
  });
}

describe("RecommendPage", () => {
  beforeEach(() => {
    // specs/019-recommend-chat-persistence: same test-isolation primitive
    // as RecommendChat.test.tsx — the store is a module singleton.
    recommendChatStore.reset();
    searchParamsValue = new URLSearchParams();
    vi.mocked(apiClient.GET).mockReset().mockImplementation(mockGetByUrl() as never);
  });

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
        outfits: [
          {
            id: null,
            occasion: "business casual",
            rationale_text: "Reply.",
            items: [],
            match_label: "great",
            meta_line: "business casual · Business casual",
          },
        ],
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

  it("019 US2: a New chat reset survives navigating away and back — still hero, not the pre-reset conversation", async () => {
    vi.mocked(apiClient.POST).mockResolvedValue({
      data: {
        thread_id: "thread-1",
        reply_text: null,
        outfits: [
          {
            id: null,
            occasion: "business casual",
            rationale_text: "Reply.",
            items: [],
            match_label: "great",
            meta_line: "business casual · Business casual",
          },
        ],
      },
      error: undefined,
      response: new Response(),
    } as never);

    const { unmount } = render(<RecommendPage />);
    await userEvent.type(await screen.findByLabelText("Message"), "business casual{Enter}");
    await userEvent.click(screen.getByText("Start styling"));
    await waitFor(() => expect(screen.getByText("Reply.")).toBeInTheDocument());
    await userEvent.click(screen.getByLabelText("New chat"));
    expect(screen.getByText("What to Wear")).toBeInTheDocument();

    // Navigate away and back — a fresh RecommendPage instance, no props.
    unmount();
    render(<RecommendPage />);

    expect(await screen.findByText("What to Wear")).toBeInTheDocument();
    expect(screen.getByLabelText("New chat")).toBeDisabled();
    expect(screen.queryByText("Reply.")).not.toBeInTheDocument();
  });

  it("019 US4: a ?thread_id= link for a thread not currently held hydrates the store and renders its turns", async () => {
    searchParamsValue = new URLSearchParams("thread_id=past-thread");
    vi.mocked(apiClient.GET).mockReset().mockImplementation(
      mockGetByUrl({
        "/api/v1/recommend/sessions/{session_id}": {
          data: {
            messages: [{ id: "m1", kind: "user_message", role: "user", text: "Rainy commute", outfits: [] }],
          },
        },
      }) as never,
    );

    render(<RecommendPage />);

    expect(await screen.findByText("Rainy commute")).toBeInTheDocument();
    expect(apiClient.GET).toHaveBeenCalledWith(
      "/api/v1/recommend/sessions/{session_id}",
      expect.objectContaining({ params: { path: { session_id: "past-thread" } } }),
    );
  });

  it("019 US4/FR-006: a ?thread_id= link matching the store's already-active thread does not re-fetch", async () => {
    recommendChatStore.hydrate("already-active", [{ id: "m1", role: "user", text: "Rainy commute" }]);
    searchParamsValue = new URLSearchParams("thread_id=already-active");

    render(<RecommendPage />);

    expect(await screen.findByText("Rainy commute")).toBeInTheDocument();
    expect(apiClient.GET).not.toHaveBeenCalledWith(
      "/api/v1/recommend/sessions/{session_id}",
      expect.anything(),
    );
  });

  it("019 US4: after resuming, navigating away and back to plain /recommend still shows the resumed conversation", async () => {
    searchParamsValue = new URLSearchParams("thread_id=past-thread");
    vi.mocked(apiClient.GET).mockReset().mockImplementation(
      mockGetByUrl({
        "/api/v1/recommend/sessions/{session_id}": {
          data: {
            messages: [{ id: "m1", kind: "user_message", role: "user", text: "Rainy commute", outfits: [] }],
          },
        },
      }) as never,
    );
    const { unmount } = render(<RecommendPage />);
    await screen.findByText("Rainy commute");

    unmount();
    searchParamsValue = new URLSearchParams(); // plain /recommend, matching an ordinary tab tap
    render(<RecommendPage />);

    expect(await screen.findByText("Rainy commute")).toBeInTheDocument();
    // Still exactly one fetch of the resumed session — the second mount
    // didn't re-fetch it (FR-006 applies to plain in-app nav too).
    expect(
      vi.mocked(apiClient.GET).mock.calls.filter((call) => call[0] === "/api/v1/recommend/sessions/{session_id}"),
    ).toHaveLength(1);
  });

  it("Chat history links to /history", async () => {
    render(<RecommendPage />);
    await screen.findByLabelText("Message");
    expect(screen.getByLabelText("Chat history").closest("a")).toHaveAttribute("href", "/history");
  });
});
