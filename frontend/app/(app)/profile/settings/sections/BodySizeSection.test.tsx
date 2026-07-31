import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BodySizeSection } from "./BodySizeSection";
import type { ProfileResponse } from "@/lib/api/profile";

const updateBodySize = vi.fn();

vi.mock("@/lib/api/profile", () => ({
  updateBodySize: (...args: unknown[]) => updateBodySize(...args),
}));

const EMPTY_PROFILE: ProfileResponse = {
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
  updateBodySize.mockReset();
});

describe("BodySizeSection", () => {
  it("shows an empty state for an unset birth date rather than an invalid date", () => {
    render(<BodySizeSection profile={EMPTY_PROFILE} disabled={false} onSaved={vi.fn()} />);

    expect(screen.getByText("Date of birth")).toBeInTheDocument();
    expect(screen.getAllByText("Not set yet").length).toBeGreaterThan(0);
  });

  it("renders all five body shape options once editing", async () => {
    render(<BodySizeSection profile={EMPTY_PROFILE} disabled={false} onSaved={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));

    expect(screen.getByRole("button", { name: "Hourglass" })).toBeInTheDocument();
  });

  it("a future birth date blocks save with a validation error", async () => {
    render(<BodySizeSection profile={EMPTY_PROFILE} disabled={false} onSaved={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const birthDateInput = screen.getByLabelText("Birth date");
    await userEvent.type(birthDateInput, "2999-01-01");

    expect(screen.getByText("Enter a date in the past.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Done" })).toBeDisabled();
    expect(updateBodySize).not.toHaveBeenCalled();
  });

  it("all fields persist together on Done", async () => {
    updateBodySize.mockResolvedValue({ ...EMPTY_PROFILE, body_shape: "hourglass", gender: "woman" });
    const onSaved = vi.fn();
    render(<BodySizeSection profile={EMPTY_PROFILE} disabled={false} onSaved={onSaved} />);

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.click(screen.getByRole("button", { name: "Hourglass" }));
    await userEvent.click(screen.getByRole("button", { name: "Woman" }));
    await userEvent.click(screen.getByRole("button", { name: "Done" }));

    expect(updateBodySize).toHaveBeenCalledWith(
      expect.objectContaining({ body_shape: "hourglass", gender: "woman" }),
    );
    expect(onSaved).toHaveBeenCalled();
  });
});
