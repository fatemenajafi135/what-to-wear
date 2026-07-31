import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AccountSection } from "./AccountSection";

const getSession = vi.fn();
const updateUser = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { getSession, updateUser } }),
}));

beforeEach(() => {
  getSession.mockReset();
  updateUser.mockReset();
  getSession.mockResolvedValue({ data: { session: { user: { email: "maya@example.com" } } } });
});

describe("AccountSection", () => {
  it("shows the current session email in read mode", async () => {
    render(<AccountSection disabled={false} />);

    await waitFor(() => expect(screen.getByText("maya@example.com")).toBeInTheDocument());
  });

  it("invalid format blocks Done and never calls updateUser", async () => {
    render(<AccountSection disabled={false} />);
    await waitFor(() => expect(screen.getByText("maya@example.com")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const input = screen.getByLabelText("Email");
    await userEvent.clear(input);
    await userEvent.type(input, "not-an-email");
    await userEvent.click(screen.getByRole("button", { name: "Done" }));

    expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument();
    expect(updateUser).not.toHaveBeenCalled();
  });

  it("valid format calls updateUser and returns to read state with the new value", async () => {
    updateUser.mockResolvedValue({ error: null });
    render(<AccountSection disabled={false} />);
    await waitFor(() => expect(screen.getByText("maya@example.com")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const input = screen.getByLabelText("Email");
    await userEvent.clear(input);
    await userEvent.type(input, "new@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Done" }));

    await waitFor(() => expect(updateUser).toHaveBeenCalledWith({ email: "new@example.com" }));
    expect(await screen.findByText("new@example.com")).toBeInTheDocument();
  });
});
