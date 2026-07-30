import { describe, it, expect, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import {
  authFieldMessages,
  validateEmail,
  validatePassword,
  validateConfirmPassword,
  useValidatedField,
} from "./auth-validation";

describe("validators", () => {
  it("requires a non-empty email", () => {
    expect(validateEmail("")).toBe(authFieldMessages.required);
  });

  it("rejects a malformed email", () => {
    expect(validateEmail("not-an-email")).toBe(authFieldMessages.emailInvalid);
  });

  it("accepts a well-formed email", () => {
    expect(validateEmail("a@example.com")).toBeUndefined();
  });

  it("rejects a password under 8 characters", () => {
    expect(validatePassword("short")).toBe(authFieldMessages.passwordTooShort);
  });

  it("accepts an 8+ character password", () => {
    expect(validatePassword("longenough")).toBeUndefined();
  });

  it("rejects a confirm-password that doesn't match", () => {
    expect(validateConfirmPassword("longenough", "different")).toBe(authFieldMessages.passwordMismatch);
  });

  it("accepts a matching confirm-password", () => {
    expect(validateConfirmPassword("longenough", "longenough")).toBeUndefined();
  });
});

describe("useValidatedField", () => {
  it("shows no error before the field is blurred, even with an invalid value", () => {
    const { result } = renderHook(() => useValidatedField(validateEmail));
    act(() => result.current.onChange("not-an-email"));
    expect(result.current.error).toBeUndefined();
  });

  it("validates on blur", () => {
    const { result } = renderHook(() => useValidatedField(validateEmail));
    act(() => result.current.onChange("not-an-email"));
    act(() => result.current.onBlur());
    expect(result.current.error).toBe(authFieldMessages.emailInvalid);
  });

  it("re-validates on every change once already errored, clearing the error once fixed", () => {
    const { result } = renderHook(() => useValidatedField(validateEmail));
    act(() => result.current.onChange("not-an-email"));
    act(() => result.current.onBlur());
    expect(result.current.error).toBe(authFieldMessages.emailInvalid);

    act(() => result.current.onChange("still-bad"));
    expect(result.current.error).toBe(authFieldMessages.emailInvalid);

    act(() => result.current.onChange("a@example.com"));
    expect(result.current.error).toBeUndefined();
  });

  it("does not re-validate on change while untouched and currently valid", () => {
    const validate = vi.fn(validateEmail);
    const { result } = renderHook(() => useValidatedField(validate));
    act(() => result.current.onChange("a"));
    act(() => result.current.onChange("a@"));
    expect(result.current.error).toBeUndefined();
    expect(validate).not.toHaveBeenCalled();
  });
});
