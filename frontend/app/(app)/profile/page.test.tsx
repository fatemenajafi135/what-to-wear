import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProfilePage from "./page";

const push = vi.fn();
const refresh = vi.fn();
const signOut = vi.fn();
const getSession = vi.fn();
const getProfile = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { signOut, getSession } }),
}));

vi.mock("@/lib/api/profile", () => ({
  getProfile: () => getProfile(),
}));

const DEFAULT_PROFILE = {
  style_tags: [],
  colour_tags: [],
  brands_to_avoid: [],
  body_shape: null,
  gender: null,
  birth_date: null,
  height: null,
  top_size: null,
  bottom_size: null,
  shoe_size: null,
  notifications_enabled: true,
};

beforeEach(() => {
  push.mockClear();
  refresh.mockClear();
  signOut.mockClear();
  getSession.mockReset();
  getProfile.mockReset();
  getSession.mockResolvedValue({ data: { session: { user: { email: "maya@example.com" } } } });
  getProfile.mockResolvedValue(DEFAULT_PROFILE);
});

describe("ProfilePage", () => {
  it("renders three cards with default values for a first-time user", async () => {
    render(<ProfilePage />);

    await waitFor(() => expect(screen.getByText("maya@example.com")).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "Account" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Style preferences" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Body & size" })).toBeInTheDocument();
  });

  it("renders saved values when present", async () => {
    getProfile.mockResolvedValue({
      ...DEFAULT_PROFILE,
      style_tags: ["Classic"],
      colour_tags: ["Pastels"],
      body_shape: "hourglass",
    });

    render(<ProfilePage />);

    await waitFor(() => expect(screen.getByText("Classic")).toBeInTheDocument());
    expect(screen.getByText("Pastels")).toBeInTheDocument();
    expect(screen.getByText("Hourglass")).toBeInTheDocument();
  });

  it("shows the error state with retry on a failed load", async () => {
    getProfile.mockRejectedValue(new Error("network error"));

    render(<ProfilePage />);

    await waitFor(() =>
      expect(screen.getByText("That didn't save. Check your connection and try again.")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("links the gear icon to /profile/settings", async () => {
    render(<ProfilePage />);

    await waitFor(() => expect(screen.getByRole("link")).toHaveAttribute("href", "/profile/settings"));
  });

  it("signs out and redirects to /signin", async () => {
    signOut.mockResolvedValue({ error: null });
    render(<ProfilePage />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => expect(signOut).toHaveBeenCalled());
    expect(push).toHaveBeenCalledWith("/signin");
  });
});
