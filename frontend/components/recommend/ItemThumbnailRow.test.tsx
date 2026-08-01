import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ItemThumbnailRow } from "./ItemThumbnailRow";

const items = [
  { id: "item-1", name: "Navy tee", category: "t-shirt", category_group: "top" as const, colors: [], color_names: [], photo_url: "https://example.com/photo.jpg" },
  { id: "item-2", name: null, category: "boots", category_group: "footwear" as const, colors: [], color_names: [], photo_url: null },
];

describe("ItemThumbnailRow", () => {
  it("renders a link per item pointing at /closet/:itemId", () => {
    render(<ItemThumbnailRow items={items} />);
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "/closet/item-1");
    expect(links[1]).toHaveAttribute("href", "/closet/item-2");
  });

  it("renders nothing for an empty item list", () => {
    const { container } = render(<ItemThumbnailRow items={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
