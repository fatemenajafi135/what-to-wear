import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/api/client";
import { AddItemFlow } from "./AddItemFlow";

vi.mock("@/lib/api/client", () => ({
  apiClient: { POST: vi.fn() },
}));
vi.mock("@/lib/useOnlineStatus", () => ({ useOnlineStatus: vi.fn(() => true) }));
vi.mock("@/lib/camera/primed", () => ({
  isCameraPrimed: vi.fn(() => true), // primed — skip the primer dialog in these flow tests
  setCameraPrimed: vi.fn(),
}));

const mockedPost = vi.mocked(apiClient.POST);

beforeEach(() => {
  mockedPost.mockReset();
  URL.createObjectURL = vi.fn(() => "blob:fake-url");
});

async function selectFile() {
  const file = new File(["fake"], "shirt.jpg", { type: "image/jpeg" });
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  await userEvent.upload(input, file);
}

describe("AddItemFlow", () => {
  it("shows the review card pre-filled after a successful scan", async () => {
    mockedPost.mockResolvedValueOnce({
      data: {
        photo_path: "user-a/x.jpg",
        extraction_ok: true,
        extracted: {
          category: "top",
          colors: ["#1b2a4a"],
          fabric: "cotton",
          formality: "casual",
          warmth: 2,
          season: ["spring"],
          pattern: "solid",
          fit: "regular",
        },
        color_names: ["navy"],
      },
      error: undefined,
      response: new Response(),
    });

    render(<AddItemFlow onClose={vi.fn()} />);
    await selectFile();

    expect(await screen.findByLabelText("Group")).toHaveValue("top");
    expect(screen.getByLabelText("Fabric")).toHaveValue("cotton");
    // The colour is a TagInput chip showing the derived name, with the
    // detected hex kept behind it.
    expect(screen.getByText("navy")).toBeInTheDocument();
    expect(screen.getByLabelText("Formality")).toHaveValue("casual");
    expect(screen.getByLabelText("Warmth")).toHaveValue("2");
  });

  it("shows the empty state (not an error) when no garment is found", async () => {
    mockedPost.mockResolvedValueOnce({
      data: {
        photo_path: "user-a/x.jpg",
        extraction_ok: false,
        extracted: {},
        color_names: [],
      },
      error: undefined,
      response: new Response(),
    });

    render(<AddItemFlow onClose={vi.fn()} />);
    await selectFile();

    expect(await screen.findByText(/I couldn't find any clothing in that photo/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retake photo" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enter manually" })).toBeInTheDocument();
  });

  it("Enter manually advances to the same blank review card", async () => {
    mockedPost.mockResolvedValueOnce({
      data: { photo_path: "user-a/x.jpg", extraction_ok: false, extracted: {}, color_names: [] },
      error: undefined,
      response: new Response(),
    });

    render(<AddItemFlow onClose={vi.fn()} />);
    await selectFile();
    await userEvent.click(await screen.findByRole("button", { name: "Enter manually" }));

    expect(screen.getByLabelText("Name")).toHaveValue("");
    expect(screen.getByLabelText("Color")).toHaveValue("");
  });

  it("shows the distinct error state on a genuine extract failure", async () => {
    mockedPost.mockResolvedValueOnce({ data: undefined, error: { detail: "boom" }, response: new Response() });

    render(<AddItemFlow onClose={vi.fn()} />);
    await selectFile();

    expect(await screen.findByText("That upload didn't go through.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("saves and closes the overlay on successful save", async () => {
    mockedPost
      .mockResolvedValueOnce({
        data: {
          photo_path: "user-a/x.jpg",
          extraction_ok: true,
          extracted: {
            category: "top",
            colors: ["#1b2a4a"],
            formality: "casual",
            warmth: 2,
            season: ["spring"],
          },
          color_names: ["navy"],
        },
        error: undefined,
        response: new Response(),
      })
      .mockResolvedValueOnce({ data: { id: "new-item" }, error: undefined, response: new Response() });

    const onClose = vi.fn();
    render(<AddItemFlow onClose={onClose} />);
    await selectFile();
    await screen.findByLabelText("Group");
    await userEvent.click(screen.getByRole("button", { name: "Save to Closet" }));

    expect(onClose).toHaveBeenCalled();
    expect(mockedPost).toHaveBeenCalledWith(
      "/api/v1/closet/items/from-upload",
      // Hex, and every detected attribute — not the six-field subset that
      // used to drop formality/warmth/season/pattern/fit (design-decisions §30).
      expect.objectContaining({
        body: expect.objectContaining({
          colors: ["#1b2a4a"],
          formality: "casual",
          warmth: 2,
          season: ["spring"],
        }),
      })
    );
  });
});
