import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ALL_FIELDS, SOURCE_URL } from "@/api";
import { JobForm } from "./job-form";

describe("controlled job submission", () => {
  it("submits only selected fields with the owned URL and one-page budget", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(<JobForm onCreate={onCreate} />);
    fireEvent.click(screen.getByLabelText("Currency", { exact: true }));
    fireEvent.click(screen.getByRole("button", { name: "Create job" }));
    await waitFor(() => expect(onCreate).toHaveBeenCalledOnce());
    expect(onCreate.mock.calls[0][0]).toEqual({
      seed_url: SOURCE_URL, page_limit: 1,
      selected_fields: ALL_FIELDS.filter((field) => field !== "currency"),
    });
    expect(onCreate.mock.calls[0][1]).toEqual(expect.any(String));
  });

  it("retains the idempotency key after a failed response even when storage is blocked", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Storage blocked"); });
    const onCreate = vi.fn().mockRejectedValueOnce(new Error("Connection lost")).mockResolvedValue(undefined);
    render(<JobForm onCreate={onCreate} />);
    fireEvent.click(screen.getByRole("button", { name: "Create job" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Connection lost");
    fireEvent.click(screen.getByRole("button", { name: "Create job" }));
    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(2));
    expect(onCreate.mock.calls[1][1]).toBe(onCreate.mock.calls[0][1]);
  });

  it("prevents another submission while the first response is pending", async () => {
    let finish = () => {};
    const onCreate = vi.fn(() => new Promise<void>((resolve) => { finish = resolve; }));
    render(<JobForm onCreate={onCreate} />);
    fireEvent.click(screen.getByRole("button", { name: "Create job" }));
    const pending = screen.getByRole("button", { name: "Submitting…" });
    expect(pending).toBeDisabled();
    fireEvent.click(pending);
    expect(onCreate).toHaveBeenCalledOnce();
    finish();
    await waitFor(() => expect(screen.getByRole("button", { name: "Create job" })).toBeEnabled());
  });
});
