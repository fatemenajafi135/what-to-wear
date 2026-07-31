import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StylePreferencesSection } from "./StylePreferencesSection";
import type { ProfileResponse } from "@/lib/api/profile";

const updateStylePreferences = vi.fn();

vi.mock("@/lib/api/profile", () => ({
  updateStylePreferences: (...args: unknown[]) => updateStylePreferences(...args),
}));

const PROFILE: ProfileResponse = {
  style_tags: ["Classic"],
  colour_tags: [],
  brands_to_avoid: [],
  notifications_enabled: true,
};

beforeEach(() => {
  updateStylePreferences.mockReset();
});

describe("StylePreferencesSection", () => {
  it("shows saved values in read mode", () => {
    render(<StylePreferencesSection profile={PROFILE} disabled={false} onSaved={vi.fn()} />);

    expect(screen.getByText("Classic")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Minimal" })).not.toBeInTheDocument();
  });

  it("Edit pre-fills the last saved values as an editable Chip picker", async () => {
    render(<StylePreferencesSection profile={PROFILE} disabled={false} onSaved={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));

    expect(screen.getByRole("button", { name: "Classic" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Minimal" })).toHaveAttribute("aria-pressed", "false");
  });

  it("Done persists the edited values and returns to read state", async () => {
    updateStylePreferences.mockResolvedValue({
      ...PROFILE,
      style_tags: ["Classic", "Minimal"],
    });
    const onSaved = vi.fn();
    render(<StylePreferencesSection profile={PROFILE} disabled={false} onSaved={onSaved} />);

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(screen.getByRole("button", { name: "Minimal" }));
    await userEvent.click(screen.getByRole("button", { name: "Done" }));

    expect(updateStylePreferences).toHaveBeenCalledWith({
      style_tags: ["Classic", "Minimal"],
      colour_tags: [],
      brands_to_avoid: [],
    });
    expect(onSaved).toHaveBeenCalledWith({ ...PROFILE, style_tags: ["Classic", "Minimal"] });
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  });

  it("abandoning edit (unmount without Done) never calls the update", async () => {
    const { unmount } = render(<StylePreferencesSection profile={PROFILE} disabled={false} onSaved={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(screen.getByRole("button", { name: "Minimal" }));
    unmount();

    expect(updateStylePreferences).not.toHaveBeenCalled();
  });

  it("an empty brands-to-avoid list is a valid, savable state", async () => {
    updateStylePreferences.mockResolvedValue(PROFILE);
    render(<StylePreferencesSection profile={PROFILE} disabled={false} onSaved={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(screen.getByRole("button", { name: "Done" }));

    expect(updateStylePreferences).toHaveBeenCalledWith(
      expect.objectContaining({ brands_to_avoid: [] }),
    );
  });
});
