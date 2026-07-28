import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Input } from "./Input";

describe("Input", () => {
  it("associates the label and calls onChange as the user types", async () => {
    const onChange = vi.fn();
    render(<Input label="Email" type="email" value="" onChange={onChange} />);
    const field = screen.getByLabelText("Email");
    await userEvent.type(field, "a");
    expect(onChange).toHaveBeenCalledWith("a");
  });

  it("shows an error message and marks the field aria-invalid", () => {
    render(
      <Input label="Email" value="bad" onChange={() => {}} error="Enter a valid email address." />,
    );
    const field = screen.getByLabelText("Email");
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument();
  });

  it("does not render both help text and error at once", () => {
    render(<Input label="Email" value="" onChange={() => {}} helpText="Help" error="Error" />);
    expect(screen.getByText("Error")).toBeInTheDocument();
    expect(screen.queryByText("Help")).not.toBeInTheDocument();
  });

  it("renders a password show/hide toggle for type=password", async () => {
    render(<Input label="Password" type="password" value="secret" onChange={() => {}} />);
    const toggle = screen.getByRole("button", { name: "Show password" });
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
    await userEvent.click(toggle);
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Hide password" })).toBeInTheDocument();
  });

  it("is disabled when the disabled prop is set", () => {
    render(<Input label="Email" value="" onChange={() => {}} disabled />);
    expect(screen.getByLabelText("Email")).toBeDisabled();
  });
});
