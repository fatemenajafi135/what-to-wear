import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SettingsPage from "./page";

const getProfile = vi.fn();
const getSession = vi.fn();

vi.mock("@/lib/api/profile", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/profile")>("@/lib/api/profile");
  return {
    ...actual,
    getProfile: () => getProfile(),
  };
});

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { getSession, updateUser: vi.fn() } }),
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
  getProfile.mockReset();
  getSession.mockReset();
  getProfile.mockResolvedValue(DEFAULT_PROFILE);
  getSession.mockResolvedValue({ data: { session: { user: { email: "maya@example.com" } } } });
});

describe("SettingsPage", () => {
  it("defaults to the Style preferences section", async () => {
    render(<SettingsPage />);

    await waitFor(() => expect(screen.getAllByText("Style preferences").length).toBeGreaterThan(0));
  });

  it("switching sections via the list shows that section's content", async () => {
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getAllByText("Style preferences").length).toBeGreaterThan(0));

    await userEvent.click(screen.getByRole("button", { name: "Notifications" }));

    expect(screen.getByText("Push notifications")).toBeInTheDocument();
  });

  it("shows the error state with retry on a failed load", async () => {
    getProfile.mockRejectedValue(new Error("network error"));

    render(<SettingsPage />);

    await waitFor(() =>
      expect(screen.getByText("That didn't save. Check your connection and try again.")).toBeInTheDocument(),
    );
  });

  it("renders all six sections in the switcher", async () => {
    render(<SettingsPage />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Account" })).toBeInTheDocument());

    expect(screen.getByRole("button", { name: "Style preferences" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Body & size" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Account" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connected accounts" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Appearance" })).toBeInTheDocument();
  });
});
