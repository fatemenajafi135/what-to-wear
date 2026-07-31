import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { ItemEditForm } from "./ItemEditForm";

vi.mock("@/lib/api/client", () => ({
  apiClient: { PATCH: vi.fn() },
}));

const mockedPatch = vi.mocked(apiClient.PATCH);

type ClosetItemView = components["schemas"]["ClosetItemView"];

const ITEM: ClosetItemView = {
  id: "item-1",
  category: "t-shirt",
  category_group: "top",
  colors: ["#1b2a4a"],
  color_names: ["navy"],
  formality: "casual",
  warmth: 1,
  season: ["spring"],
  fabric: "cotton",
  pattern: null,
  fit: null,
  name: "Navy tee",
  notes: "A bit worn",
  source: "upload",
  photo_path: null,
  favorite: false,
};

beforeEach(() => {
  mockedPatch.mockReset();
});

describe("ItemEditForm", () => {
  it("pre-fills every field from the item", () => {
    render(<ItemEditForm item={ITEM} isOnline onSaved={vi.fn()} />);
    expect(screen.getByLabelText("Name")).toHaveValue("Navy tee");
    expect(screen.getByLabelText("Group")).toHaveValue("t-shirt");
    expect(screen.getByLabelText("Fabric")).toHaveValue("cotton");
    expect(screen.getByLabelText("Colour")).toHaveValue("navy");
    expect(screen.getByLabelText("Notes")).toHaveValue("A bit worn");
  });

  it("submits only the changed field", async () => {
    mockedPatch.mockResolvedValue({ data: { ...ITEM, notes: "Needs ironing" }, error: undefined } as never);
    const onSaved = vi.fn();
    render(<ItemEditForm item={ITEM} isOnline onSaved={onSaved} />);

    await userEvent.clear(screen.getByLabelText("Notes"));
    await userEvent.type(screen.getByLabelText("Notes"), "Needs ironing");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(mockedPatch).toHaveBeenCalledWith(
      "/api/v1/closet/items/{item_id}",
      expect.objectContaining({
        params: { path: { item_id: "item-1" } },
        body: { notes: "Needs ironing" },
      }),
    );
    expect(onSaved).toHaveBeenCalledWith({ ...ITEM, notes: "Needs ironing" });
  });

  it("setting a Category chip writes the bare group name", async () => {
    mockedPatch.mockResolvedValue({ data: ITEM, error: undefined } as never);
    render(<ItemEditForm item={ITEM} isOnline onSaved={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Footwear" }));
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(mockedPatch).toHaveBeenCalledWith(
      "/api/v1/closet/items/{item_id}",
      expect.objectContaining({ body: { category: "footwear" } }),
    );
  });

  it("disables Save changes while offline", () => {
    render(<ItemEditForm item={ITEM} isOnline={false} onSaved={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });
});
