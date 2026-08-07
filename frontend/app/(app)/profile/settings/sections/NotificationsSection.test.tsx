import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NotificationsSection } from "./NotificationsSection";
import type { ProfileResponse } from "@/lib/api/profile";

const updateNotifications = vi.fn();

vi.mock("@/lib/api/profile", () => ({
  updateNotifications: (...args: unknown[]) => updateNotifications(...args),
}));

const PROFILE: ProfileResponse = {
  style_tags: [],
  colour_tags: [],
  brands_to_avoid: [],
  notifications_enabled: true,
};

beforeEach(() => {
  updateNotifications.mockReset();
});

describe("NotificationsSection", () => {
  it("has no Edit/Done control", () => {
    render(<NotificationsSection profile={PROFILE} disabled={false} onSaved={vi.fn()} />);

    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
  });

  it("toggling calls the update immediately, with no separate save step", async () => {
    updateNotifications.mockResolvedValue({ ...PROFILE, notifications_enabled: false });
    const onSaved = vi.fn();
    render(<NotificationsSection profile={PROFILE} disabled={false} onSaved={onSaved} />);

    await userEvent.click(screen.getByRole("switch"));

    expect(updateNotifications).toHaveBeenCalledWith({ notifications_enabled: false });
    expect(onSaved).toHaveBeenCalledWith({ ...PROFILE, notifications_enabled: false });
  });

  it("defaults to on for a brand-new user", () => {
    render(<NotificationsSection profile={PROFILE} disabled={false} onSaved={vi.fn()} />);

    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
  });
});
