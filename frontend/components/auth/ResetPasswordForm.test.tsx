import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResetPasswordForm } from "./ResetPasswordForm";

const verifyOtp = vi.fn();
const updateUser = vi.fn();
const signOut = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { verifyOtp, updateUser, signOut } }),
}));

beforeEach(() => {
  verifyOtp.mockClear();
  updateUser.mockClear();
  signOut.mockClear();
});

describe("ResetPasswordForm", () => {
  it("shows the error state and a link back to /forgot-password for an invalid/expired token", async () => {
    verifyOtp.mockResolvedValue({ error: { message: "expired" } });
    render(<ResetPasswordForm token="bad-token" />);

    await waitFor(() => expect(screen.getByText("This link has expired. Request a new one.")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Resend link" })).toHaveAttribute("href", "/forgot-password");
  });

  it("shows the password form for a valid token, and the success state after submit, without leaving a session", async () => {
    verifyOtp.mockResolvedValue({ error: null });
    updateUser.mockResolvedValue({ error: null });
    render(<ResetPasswordForm token="good-token" />);

    await waitFor(() => expect(screen.getByLabelText("New password")).toBeInTheDocument());
    await userEvent.type(screen.getByLabelText("New password"), "newlongpassword");
    await userEvent.type(screen.getByLabelText("Confirm password"), "newlongpassword");
    await userEvent.click(screen.getByRole("button", { name: "Update password" }));

    await waitFor(() => expect(screen.getByText("Your password has been updated.")).toBeInTheDocument());
    expect(signOut).toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/signin");
  });

  it("blocks submission when the passwords don't match", async () => {
    verifyOtp.mockResolvedValue({ error: null });
    render(<ResetPasswordForm token="good-token" />);

    await waitFor(() => expect(screen.getByLabelText("New password")).toBeInTheDocument());
    await userEvent.type(screen.getByLabelText("New password"), "newlongpassword");
    await userEvent.type(screen.getByLabelText("Confirm password"), "different");
    await userEvent.click(screen.getByRole("button", { name: "Update password" }));

    expect(screen.getByText("These passwords do not match.")).toBeInTheDocument();
    expect(updateUser).not.toHaveBeenCalled();
  });
});
