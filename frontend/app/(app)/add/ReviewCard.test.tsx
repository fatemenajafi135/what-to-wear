import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ReviewCard } from "./ReviewCard";

/** A complete scan result — what the VLM produces for a garment it read
 * successfully. Every one of these eight attributes must survive to onSave;
 * five of them used to be dropped between here and the request body. */
const SCANNED = {
  name: "",
  category: "t-shirt",
  colors: ["#22345d"],
  formality: "smart_casual",
  warmth: "2",
  season: ["spring", "autumn"] as ("spring" | "summer" | "autumn" | "winter")[],
  fabric: "cotton",
  pattern: "solid",
  fit: "regular",
  notes: "",
};

describe("ReviewCard", () => {
  it("pre-fills every scanned attribute, not just the six-field subset", () => {
    render(
      <ReviewCard
        photoUrl="blob:fake"
        initial={SCANNED}
        saveLabel="Save to Closet"
        onSave={vi.fn()}
      />
    );
    expect(screen.getByLabelText("Group")).toHaveValue("t-shirt");
    expect(screen.getByLabelText("Fabric")).toHaveValue("cotton");
    expect(screen.getByRole("button", { name: "Smart casual" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Warmth 2 — Mild" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Pattern")).toHaveValue("solid");
    expect(screen.getByLabelText("Fit")).toHaveValue("regular");
    expect(screen.getByRole("button", { name: "Spring" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Summer" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByLabelText("Color 1 hex")).toHaveValue("#22345d");
  });

  it("sends all eight attributes on save, with colour as the DETECTED hex", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <ReviewCard
        photoUrl="blob:fake"
        initial={SCANNED}
        saveLabel="Save to Closet"
        onSave={onSave}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));

    expect(onSave).toHaveBeenCalledWith({
      name: "",
      category: "t-shirt",
      // #22345d, not navy's palette hex #1b2a4a — the round-trip through a
      // name used to destroy the detected value.
      colors: ["#22345d"],
      formality: "smart_casual",
      warmth: "2",
      season: ["spring", "autumn"],
      fabric: "cotton",
      pattern: "solid",
      fit: "regular",
      notes: "",
    });
  });

  it("starts blank when initial is empty (no garment found / Enter manually)", () => {
    render(<ReviewCard photoUrl="blob:fake" initial={{}} saveLabel="Save to Closet" onSave={vi.fn()} />);
    expect(screen.getByLabelText("Name")).toHaveValue("");
    // Nothing preselected — a chip group can show "not detected" honestly,
    // where a <select> would have silently landed on its first option.
    expect(screen.getByRole("button", { name: "Casual" })).toHaveAttribute("aria-pressed", "false");
  });

  it("keeps a colour the user typed themselves as hex", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <ReviewCard
        photoUrl="blob:fake"
        initial={{ ...SCANNED, colors: [] }}
        saveLabel="Save to Closet"
        onSave={onSave}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: "Add color" }));
    await userEvent.clear(screen.getByLabelText("Color 1 hex"));
    await userEvent.type(screen.getByLabelText("Color 1 hex"), "#36454F");
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ colors: ["#36454f"] }));
  });

  it("blocks save on a malformed hex, without calling onSave", async () => {
    const onSave = vi.fn();
    render(
      <ReviewCard
        photoUrl="blob:fake"
        initial={{ ...SCANNED, colors: [] }}
        saveLabel="Save to Closet"
        onSave={onSave}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: "Add color" }));
    await userEvent.clear(screen.getByLabelText("Color 1 hex"));
    await userEvent.type(screen.getByLabelText("Color 1 hex"), "mauve");
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));

    expect(screen.getByText(/needs to be a hex code/)).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("blocks save and shows a required message when colour is left blank", async () => {
    const onSave = vi.fn();
    render(
      <ReviewCard
        photoUrl="blob:fake"
        initial={{ ...SCANNED, colors: [] }}
        saveLabel="Save to Closet"
        onSave={onSave}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));
    expect(screen.getByText("This field is required.")).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  // Colour sits well above the submit button, so on a phone the button can
  // be tapped with the error rendered off-screen — which reads as "the
  // button does nothing".
  it("moves focus to Color when validation blocks the save", async () => {
    render(
      <ReviewCard
        photoUrl="blob:fake"
        initial={{ ...SCANNED, colors: [] }}
        saveLabel="Save to Closet"
        onSave={vi.fn()}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));
    // No rows yet, so the only thing to move to is the control that adds one.
    expect(screen.getByRole("button", { name: "Add color" })).toHaveFocus();
  });

  // The legacy form's SC-003 guarantee: an item saved through the scan flow
  // has every attribute populated, none blank.
  it("blocks save when the scan failed to find formality, warmth or season", async () => {
    const onSave = vi.fn();
    render(
      <ReviewCard
        photoUrl="blob:fake"
        initial={{ category: "top", colors: ["#22345d"] }}
        saveLabel="Save to Closet"
        onSave={onSave}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));

    expect(screen.getByText(/I still need Category, Formality, Warmth and Season/)).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("clicking Category chips sets both the chip and the Group input", async () => {
    render(<ReviewCard photoUrl="blob:fake" initial={{}} saveLabel="Save to Closet" onSave={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Outerwear" }));
    expect(screen.getByLabelText("Group")).toHaveValue("outerwear");
    expect(screen.getByRole("button", { name: "Outerwear" })).toHaveAttribute("aria-pressed", "true");
  });

  it("toggles a season chip off on a second click", async () => {
    render(
      <ReviewCard
        photoUrl="blob:fake"
        initial={SCANNED}
        saveLabel="Save to Closet"
        onSave={vi.fn()}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: "Spring" }));
    expect(screen.getByRole("button", { name: "Spring" })).toHaveAttribute("aria-pressed", "false");
  });

  it("moves focus to the offending hex field when one is malformed", async () => {
    render(<ReviewCard photoUrl="blob:fake" initial={SCANNED} saveLabel="Save to Closet" onSave={vi.fn()} />);
    await userEvent.clear(screen.getByLabelText("Color 1 hex"));
    await userEvent.type(screen.getByLabelText("Color 1 hex"), "nope");
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));

    expect(screen.getByLabelText("Color 1 hex")).toHaveFocus();
  });

  it("renders the Error treatment when saveError is true", () => {
    render(
      <ReviewCard photoUrl="blob:fake" initial={SCANNED} saveLabel="Save to Closet" onSave={vi.fn()} saveError />
    );
    // Button's error state swaps its label for `errorLabel` ("Try again").
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save to Closet" })).not.toBeInTheDocument();
  });
});
