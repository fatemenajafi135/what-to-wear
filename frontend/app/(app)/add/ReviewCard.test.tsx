import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ReviewCard } from "./ReviewCard";

describe("ReviewCard", () => {
  it("pre-fills fields from the scan result", () => {
    render(
      <ReviewCard
        photoUrl="blob:fake"
        initial={{ name: "Navy tee", category: "top", fabric: "cotton", color: "navy", notes: "" }}
        saveLabel="Save to Closet"
        onSave={vi.fn()}
      />
    );
    expect(screen.getByLabelText("Name")).toHaveValue("Navy tee");
    expect(screen.getByLabelText("Fabric")).toHaveValue("cotton");
    expect(screen.getByLabelText("Color")).toHaveValue("navy");
  });

  it("starts blank when initial is empty (no garment found / Enter manually)", () => {
    render(<ReviewCard photoUrl="blob:fake" initial={{}} saveLabel="Save to Closet" onSave={vi.fn()} />);
    expect(screen.getByLabelText("Name")).toHaveValue("");
    expect(screen.getByLabelText("Color")).toHaveValue("");
  });

  it("submits the edited fields on save", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <ReviewCard
        photoUrl="blob:fake"
        initial={{ name: "", category: "", fabric: "", color: "", notes: "" }}
        saveLabel="Save to Closet"
        onSave={onSave}
      />
    );
    await userEvent.type(screen.getByLabelText("Name"), "My blazer");
    await userEvent.type(screen.getByLabelText("Color"), "navy");
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ name: "My blazer", color: "navy" })
    );
  });

  it("blocks save and shows an error for an unrecognized color, without calling onSave", async () => {
    const onSave = vi.fn();
    render(
      <ReviewCard
        photoUrl="blob:fake"
        initial={{ name: "", category: "", fabric: "", color: "", notes: "" }}
        saveLabel="Save to Closet"
        onSave={onSave}
      />
    );
    await userEvent.type(screen.getByLabelText("Color"), "mauve");
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));

    expect(screen.getByText(/I don't recognize that color/)).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("blocks save and shows a required message when color is left blank", async () => {
    const onSave = vi.fn();
    render(
      <ReviewCard
        photoUrl="blob:fake"
        initial={{ name: "", category: "", fabric: "", color: "", notes: "" }}
        saveLabel="Save to Closet"
        onSave={onSave}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));
    expect(screen.getByText("This field is required.")).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("clicking Category chips sets both the chip and the Group input", async () => {
    render(
      <ReviewCard
        photoUrl="blob:fake"
        initial={{ name: "", category: "", fabric: "", color: "", notes: "" }}
        saveLabel="Save to Closet"
        onSave={vi.fn()}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: "Outerwear" }));
    expect(screen.getByLabelText("Group")).toHaveValue("outerwear");
  });

  it("renders the Error treatment when saveError is true", () => {
    render(
      <ReviewCard
        photoUrl="blob:fake"
        initial={{}}
        saveLabel="Save to Closet"
        onSave={vi.fn()}
        saveError
      />
    );
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
