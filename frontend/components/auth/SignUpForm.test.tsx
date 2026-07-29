import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SignUpForm } from "./SignUpForm";

const push = vi.fn();
const refresh = vi.fn();
const signUp = vi.fn();
const signInWithOAuth = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { signUp, signInWithOAuth } }),
}));

beforeEach(() => {
  push.mockClear();
  refresh.mockClear();
  signUp.mockClear();
  signInWithOAuth.mockClear();
});

describe("SignUpForm", () => {
  it("shows field errors only after blur, not while typing", async () => {
    render(<SignUpForm />);
    const email = screen.getByLabelText("Email");
    await userEvent.type(email, "not-an-email");
    expect(screen.queryByText("Enter a valid email address.")).not.toBeInTheDocument();
    await userEvent.tab();
    expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument();
  });

  it("submits email and password to supabase.auth.signUp and redirects on success", async () => {
    signUp.mockResolvedValue({ error: null });
    render(<SignUpForm />);

    await userEvent.type(screen.getByLabelText("Email"), "new@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "longenough");
    await userEvent.type(screen.getByLabelText("Confirm password"), "longenough");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() =>
      expect(signUp).toHaveBeenCalledWith({ email: "new@example.com", password: "longenough" }),
    );
    expect(push).toHaveBeenCalledWith("/recommend");
  });

  it("renders a Banner with the sign-up error copy and does not clear entered values on failure", async () => {
    signUp.mockResolvedValue({ error: { message: "already registered" } });
    render(<SignUpForm />);

    await userEvent.type(screen.getByLabelText("Email"), "taken@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "longenough");
    await userEvent.type(screen.getByLabelText("Confirm password"), "longenough");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() =>
      expect(
        screen.getByText("We couldn't complete your sign-up with those details. Check them and try again, or sign in below."),
      ).toBeInTheDocument(),
    );
    expect(push).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Email")).toHaveValue("taken@example.com");
  });

  it("links to /signin for an existing account", () => {
    render(<SignUpForm />);
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/signin");
  });

  it("calls signInWithOAuth with the google provider and an /auth/callback redirect when the Google button is clicked", async () => {
    render(<SignUpForm />);
    await userEvent.click(screen.getByRole("button", { name: "Continue with Google" }));

    expect(signInWithOAuth).toHaveBeenCalledWith({
      provider: "google",
      options: { redirectTo: expect.stringContaining("/auth/callback") },
    });
  });

  it("blocks submission and shows all field errors when the passwords don't match", async () => {
    render(<SignUpForm />);
    await userEvent.type(screen.getByLabelText("Email"), "new@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "longenough");
    await userEvent.type(screen.getByLabelText("Confirm password"), "different");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(screen.getByText("These passwords do not match.")).toBeInTheDocument();
    expect(signUp).not.toHaveBeenCalled();
  });
});
