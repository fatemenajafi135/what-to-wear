import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RecommendChat } from "./RecommendChat";
import * as recommendChatStore from "@/lib/recommend/recommendChatStore";
import * as pickedEventStore from "@/lib/calendar/pickedEventStore";
import { formatEventTime } from "@/lib/calendar/formatEventTime";

vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: () => Promise.resolve({ data: { session: { user: { email: "maya@example.com" } } } }) },
  }),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import { apiClient } from "@/lib/api/client";

function mockGetByUrl(url: string) {
  if (url === "/api/v1/recommend/readiness") {
    return Promise.resolve({ data: { ready: true, sparse: false, missing: [] } });
  }
  return Promise.resolve({ data: { picked: false, event: null } });
}

const mockOutfit = {
  id: null,
  occasion: "business casual",
  rationale_text: "A relaxed pairing that works well here.",
  items: [
    {
      id: "item-1",
      name: "Navy tee",
      category: "t-shirt",
      category_group: "top",
      colors: [],
      color_names: [],
      photo_url: null,
      photo_background_color: null,
    },
  ],
  match_label: "great",
  meta_line: "business casual · Business casual",
};

const defaultTurnResponse = {
  data: {
    thread_id: "thread-1",
    reply_text: "Got it — what's the occasion?",
    occasion: null,
    formality: null,
    mood: null,
    temp_c: null,
    location: null,
  },
  error: undefined,
  response: new Response(),
};

const defaultStylingResponse = {
  data: { thread_id: "thread-1", reply_text: null, wrap_up_text: "Styling for business casual.", outfits: [mockOutfit] },
  error: undefined,
  response: new Response(),
};

/**
 * Every composer send now fires `POST /recommend/turns` in addition to
 * whatever "Start styling" fires (`POST /recommend/messages`) — this
 * dispatches by URL, mirroring `mockGetByUrl` above, rather than relying on
 * call order (feature 016 changed how many POST calls one interaction makes).
 */
function mockPostByUrl(overrides: { turns?: unknown; messages?: unknown } = {}) {
  return vi.fn((url: string) => {
    if (url === "/api/v1/recommend/turns") {
      return Promise.resolve(overrides.turns ?? defaultTurnResponse);
    }
    if (url === "/api/v1/recommend/messages") {
      return Promise.resolve(overrides.messages ?? defaultStylingResponse);
    }
    throw new Error(`unmocked POST ${url}`);
  });
}

describe("RecommendChat", () => {
  beforeEach(() => {
    // specs/019-recommend-chat-persistence: conversation state now lives in
    // a module singleton, which Vitest does not reset between `it()` cases
    // in the same file — reset it explicitly so tests don't leak state into
    // one another (the same primitive "New chat" uses in production).
    recommendChatStore.reset();
    // specs/020-calendar-pick-to-recommend: same reason — RecommendCalendarContext now reads
    // a module singleton (write-through, not fetch-on-mount) instead of calling
    // `apiClient.GET` itself on every render.
    pickedEventStore.reset();
    vi.mocked(apiClient.POST).mockReset().mockImplementation(mockPostByUrl() as never);
    vi.mocked(apiClient.GET).mockReset().mockImplementation(mockGetByUrl as never);
    Object.defineProperty(window.navigator, "onLine", { value: true, configurable: true });
  });

  it("full happy path: hero -> compose gets a reply -> Start styling -> wrap-up then pager", async () => {
    render(<RecommendChat />);
    await userEvent.type(await screen.findByLabelText("Message"), "business casual{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Got it — what's the occasion?")).toBeInTheDocument();
    });

    const startButton = screen.getByText("Start styling");
    expect(startButton).toBeEnabled();
    await userEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByText("Styling for business casual.")).toBeInTheDocument();
      expect(screen.getByText(/A relaxed pairing that works well here\./)).toBeInTheDocument();
    });
    expect(screen.queryByText(/\[\d+]/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Navy tee" })).toHaveAttribute("href", "/closet/item-1");

    expect(apiClient.POST).toHaveBeenCalledWith(
      "/api/v1/recommend/turns",
      expect.objectContaining({ body: { message: "business casual", thread_id: null } }),
    );
    expect(apiClient.POST).toHaveBeenCalledWith(
      "/api/v1/recommend/messages",
      expect.objectContaining({ body: { message: "business casual", thread_id: "thread-1" } }),
    );
  });

  it("disables the composer and shows Thinking… while a turn is in flight, re-enabling on reply", async () => {
    let resolveTurn!: (value: unknown) => void;
    vi.mocked(apiClient.POST).mockImplementation(
      mockPostByUrl({ turns: new Promise((resolve) => (resolveTurn = resolve)) }) as never,
    );

    render(<RecommendChat />);
    const input = await screen.findByLabelText("Message");
    await userEvent.type(input, "business casual{Enter}");

    expect(input).toBeDisabled();
    expect(screen.getByLabelText("Sending")).toBeDisabled();
    expect(screen.getByText("Thinking…")).toBeInTheDocument();

    resolveTurn(defaultTurnResponse);

    await waitFor(() => {
      expect(input).not.toBeDisabled();
    });
    expect(screen.queryByText("Thinking…")).not.toBeInTheDocument();
    expect(screen.getByText("Got it — what's the occasion?")).toBeInTheDocument();
  });

  it("a failed conversational turn leaves the composer usable and does not add a bubble", async () => {
    vi.mocked(apiClient.POST).mockImplementation(
      mockPostByUrl({ turns: { data: undefined, error: { detail: "boom" }, response: new Response(null, { status: 500 }) } }) as never,
    );

    render(<RecommendChat />);
    const input = await screen.findByLabelText("Message");
    await userEvent.type(input, "business casual{Enter}");

    await waitFor(() => {
      expect(input).not.toBeDisabled();
    });
    expect(screen.queryByText("Thinking…")).not.toBeInTheDocument();
    // "Start styling" still works from what was already gathered (SC-005) —
    // it becomes reachable because a user message still exists.
    expect(screen.getByText("Start styling")).toBeEnabled();
  });

  it("zero-outfit reply renders the wrap-up, reply_text, and an Add-item link, with no thumbnails", async () => {
    vi.mocked(apiClient.POST).mockImplementation(
      mockPostByUrl({
        messages: {
          data: {
            thread_id: "thread-1",
            reply_text: "Your closet doesn't have enough items to assemble an outfit for this request.",
            wrap_up_text: "Styling for black tie gala.",
            outfits: [],
          },
          error: undefined,
          response: new Response(),
        },
      }) as never,
    );

    render(<RecommendChat />);
    await userEvent.type(await screen.findByLabelText("Message"), "black tie gala{Enter}");
    await waitFor(() => expect(screen.getByText("Got it — what's the occasion?")).toBeInTheDocument());
    await userEvent.click(screen.getByText("Start styling"));

    await waitFor(() => {
      expect(screen.getByText("Styling for black tie gala.")).toBeInTheDocument();
      expect(
        screen.getByText("Your closet doesn't have enough items to assemble an outfit for this request."),
      ).toBeInTheDocument();
    });
    expect(screen.queryByRole("link", { name: "Navy tee" })).not.toBeInTheDocument();
    expect(screen.getByText("Add items to your closet")).toBeInTheDocument();
  });

  it("Start-styling error path shows retry, and retry re-issues the same request", async () => {
    vi.mocked(apiClient.POST).mockImplementation(
      mockPostByUrl({
        messages: { data: undefined, error: { detail: "boom" }, response: new Response(null, { status: 500 }) },
      }) as never,
    );

    render(<RecommendChat />);
    await userEvent.type(await screen.findByLabelText("Message"), "business casual{Enter}");
    await waitFor(() => expect(screen.getByText("Got it — what's the occasion?")).toBeInTheDocument());
    await userEvent.click(screen.getByText("Start styling"));

    await waitFor(() => {
      expect(screen.getByText("Something went wrong pulling that together.")).toBeInTheDocument();
    });

    vi.mocked(apiClient.POST).mockImplementation(mockPostByUrl() as never);
    await userEvent.click(screen.getByText("Try again"));

    await waitFor(() => {
      expect(screen.getByText(/A relaxed pairing that works well here\./)).toBeInTheDocument();
    });
    // The failed attempt plus the retry — both go through /recommend/messages.
    expect(
      vi.mocked(apiClient.POST).mock.calls.filter((call) => call[0] === "/api/v1/recommend/messages"),
    ).toHaveLength(2);
  });

  it("Start styling is hidden in the hero state (0 messages)", async () => {
    render(<RecommendChat />);
    await screen.findByLabelText("Message");
    expect(screen.queryByText("Start styling")).not.toBeInTheDocument();
  });

  it("shows the insufficient-closet gate and no composer when the closet isn't ready", async () => {
    vi.mocked(apiClient.GET).mockReset().mockImplementation(((url: string) =>
      url === "/api/v1/recommend/readiness"
        ? Promise.resolve({ data: { ready: false, sparse: false, missing: ["a pair of shoes"] } })
        : Promise.resolve({ data: { picked: false, event: null } })) as never);

    render(<RecommendChat />);
    expect(await screen.findByText("Add items to your closet")).toBeInTheDocument();
    expect(screen.queryByLabelText("Message")).not.toBeInTheDocument();
  });

  it("shows the sparse-closet banner when ready but sparse", async () => {
    vi.mocked(apiClient.GET).mockReset().mockImplementation(((url: string) =>
      url === "/api/v1/recommend/readiness"
        ? Promise.resolve({ data: { ready: true, sparse: true, missing: [] } })
        : Promise.resolve({ data: { picked: false, event: null } })) as never);

    render(<RecommendChat />);
    await screen.findByLabelText("Message");
    expect(screen.getByText(/working with a small closet/)).toBeInTheDocument();
  });

  it("US5: renders the calendar context line in the hero state", async () => {
    render(<RecommendChat />);
    expect(await screen.findByText("Style for an event from calendar")).toBeInTheDocument();
  });

  it("US5: renders the calendar context line in the chat state too", async () => {
    render(<RecommendChat />);
    await userEvent.type(await screen.findByLabelText("Message"), "business casual{Enter}");
    expect(screen.getByText("Style for an event from calendar")).toBeInTheDocument();
  });

  it("US5: shows the picked event when one exists", async () => {
    vi.mocked(apiClient.GET).mockReset().mockImplementation(((url: string) =>
      url === "/api/v1/recommend/readiness"
        ? Promise.resolve({ data: { ready: true, sparse: false, missing: [] } })
        : Promise.resolve({
            data: { picked: true, event: { title: "Dinner with Sam" } },
          })) as never);

    render(<RecommendChat />);
    expect(await screen.findByText(/Styling for Dinner with Sam · Change/)).toBeInTheDocument();
  });

  it("US2: a second Start-styling call echoes the first response's thread_id", async () => {
    render(<RecommendChat />);
    await userEvent.type(await screen.findByLabelText("Message"), "business casual{Enter}");
    await waitFor(() => expect(screen.getByText("Got it — what's the occasion?")).toBeInTheDocument());
    await userEvent.click(screen.getByText("Start styling"));
    await waitFor(() => {
      expect(screen.getByText(/A relaxed pairing that works well here\./)).toBeInTheDocument();
    });

    await userEvent.type(await screen.findByLabelText("Message"), "something warmer{Enter}");
    await waitFor(() => expect(apiClient.POST).toHaveBeenCalledWith("/api/v1/recommend/turns", expect.anything()));
    await userEvent.click(screen.getByText("Start styling"));

    await waitFor(() => {
      expect(
        vi.mocked(apiClient.POST).mock.calls.filter((call) => call[0] === "/api/v1/recommend/messages"),
      ).toHaveLength(2);
    });
    const secondStylingCall = vi
      .mocked(apiClient.POST)
      .mock.calls.filter((call) => call[0] === "/api/v1/recommend/messages")[1];
    expect(secondStylingCall?.[1]).toMatchObject({
      body: { message: "something warmer", thread_id: "thread-1" },
    });
  });

  it("011 US3: a message sent after resuming carries the resumed thread_id, verified at the request level", async () => {
    // specs/019-recommend-chat-persistence: resuming now hydrates the
    // shared store directly (page.tsx's job) rather than being seeded via
    // component props — RecommendChat has no props of its own anymore.
    recommendChatStore.hydrate("resumed-thread", [{ id: "m1", role: "user", text: "Rainy commute" }]);
    render(<RecommendChat />);

    // Resuming shows the prior turn immediately (chat state, not the hero) —
    // "New chat" correctness depends on this, not asserted by reading a reply.
    expect(await screen.findByText("Rainy commute")).toBeInTheDocument();

    await userEvent.type(await screen.findByLabelText("Message"), "something warmer{Enter}");
    await waitFor(() =>
      expect(apiClient.POST).toHaveBeenCalledWith(
        "/api/v1/recommend/turns",
        expect.objectContaining({ body: { message: "something warmer", thread_id: "resumed-thread" } }),
      ),
    );
    await userEvent.click(screen.getByText("Start styling"));

    await waitFor(() =>
      expect(apiClient.POST).toHaveBeenCalledWith(
        "/api/v1/recommend/messages",
        expect.objectContaining({ body: { message: "something warmer", thread_id: "resumed-thread" } }),
      ),
    );
  });

  it("019 US1: state survives an unmount/remount — no hero flash, no re-fetch of the conversation", async () => {
    const { unmount } = render(<RecommendChat />);
    await userEvent.type(await screen.findByLabelText("Message"), "business casual{Enter}");
    await waitFor(() => expect(screen.getByText("Got it — what's the occasion?")).toBeInTheDocument());
    await userEvent.click(screen.getByText("Start styling"));
    await waitFor(() => expect(screen.getByText("Styling for business casual.")).toBeInTheDocument());

    unmount();
    const turnCallsBeforeRemount = vi
      .mocked(apiClient.POST)
      .mock.calls.filter((call) => call[0] === "/api/v1/recommend/turns").length;

    // A fresh instance, exactly like page.tsx mounting a new `RecommendChat`
    // on navigating back to /recommend — no props seed it; the store does.
    // Readiness itself still refetches on this new mount (FR-009) — the
    // fresh instance briefly shows its own loading skeleton for that call,
    // never the hero state, before the persisted conversation renders.
    render(<RecommendChat />);

    expect(screen.queryByText("What to Wear")).not.toBeInTheDocument(); // no hero-state flash
    await waitFor(() => expect(screen.getByText("Got it — what's the occasion?")).toBeInTheDocument());
    expect(screen.getByText("Styling for business casual.")).toBeInTheDocument();
    expect(screen.getByText(/A relaxed pairing that works well here\./)).toBeInTheDocument();
    expect(
      vi.mocked(apiClient.POST).mock.calls.filter((call) => call[0] === "/api/v1/recommend/turns").length,
    ).toBe(turnCallsBeforeRemount); // no new network call for the conversation itself
  });

  it("019 US1/FR-007: a turn response that arrives after unmount still lands, once, in the remounted instance", async () => {
    let resolveTurn!: (value: unknown) => void;
    vi.mocked(apiClient.POST).mockImplementation(
      mockPostByUrl({ turns: new Promise((resolve) => (resolveTurn = resolve)) }) as never,
    );

    const { unmount } = render(<RecommendChat />);
    await userEvent.type(await screen.findByLabelText("Message"), "business casual{Enter}");
    expect(screen.getByText("Thinking…")).toBeInTheDocument();

    // Navigate away before the response arrives.
    unmount();
    resolveTurn(defaultTurnResponse);

    render(<RecommendChat />);

    await waitFor(() => {
      expect(screen.getByText("Got it — what's the occasion?")).toBeInTheDocument();
    });
    expect(screen.queryByText("Thinking…")).not.toBeInTheDocument();
    expect(screen.getAllByText("Got it — what's the occasion?")).toHaveLength(1); // not duplicated
  });

  it("019 US1/FR-009: readiness re-fetches and reflects a changed closet on remount, independent of the persisted conversation", async () => {
    const { unmount } = render(<RecommendChat />);
    await userEvent.type(await screen.findByLabelText("Message"), "business casual{Enter}");
    await waitFor(() => expect(screen.getByText("Got it — what's the occasion?")).toBeInTheDocument());
    unmount();

    // The closet changed while the user was away — readiness now reports sparse.
    vi.mocked(apiClient.GET).mockReset().mockImplementation(((url: string) =>
      url === "/api/v1/recommend/readiness"
        ? Promise.resolve({ data: { ready: true, sparse: true, missing: [] } })
        : Promise.resolve({ data: { picked: false, event: null } })) as never);

    render(<RecommendChat />);

    expect(await screen.findByText(/working with a small closet/)).toBeInTheDocument();
    // The conversation itself is unaffected by the readiness refetch.
    expect(screen.getByText("Got it — what's the occasion?")).toBeInTheDocument();
  });

  it("020 US3: pre-fills the composer with a complete message from a picked event, including location", async () => {
    pickedEventStore.set({
      google_event_id: "e1",
      title: "Dinner with Ana",
      start: "2026-08-14T20:00:00Z",
      location: "Tanto",
    });

    render(<RecommendChat />);

    const input = (await screen.findByLabelText("Message")) as HTMLInputElement;
    await waitFor(() =>
      expect(input.value).toBe(`I want an outfit for Dinner with Ana on ${formatEventTime("2026-08-14T20:00:00Z")} at Tanto`),
    );
  });

  it("020 US3: pre-fills the composer without a trailing 'at' when the picked event has no location", async () => {
    pickedEventStore.set({
      google_event_id: "e1",
      title: "Dinner with Ana",
      start: "2026-08-14T20:00:00Z",
      location: null,
    });

    render(<RecommendChat />);

    const input = (await screen.findByLabelText("Message")) as HTMLInputElement;
    await waitFor(() =>
      expect(input.value).toBe(`I want an outfit for Dinner with Ana on ${formatEventTime("2026-08-14T20:00:00Z")}`),
    );
  });

  it("020 US3: no pre-fill in a fresh conversation with no picked event", async () => {
    pickedEventStore.set(null);
    render(<RecommendChat />);
    const input = await screen.findByLabelText("Message");
    expect(input).toHaveValue("");
  });

  it("020 US3: no pre-fill once the conversation already has a user message (FR-011)", async () => {
    pickedEventStore.set({
      google_event_id: "e1",
      title: "Dinner with Ana",
      start: "2026-08-14T20:00:00Z",
      location: "Tanto",
    });
    recommendChatStore.hydrate("thread-already-active", [{ id: "m1", role: "user", text: "something casual" }]);

    render(<RecommendChat />);

    const input = await screen.findByLabelText("Message");
    expect(input).toHaveValue("");
  });
});
