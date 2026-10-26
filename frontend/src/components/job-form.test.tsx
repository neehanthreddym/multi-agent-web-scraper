import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ALL_FIELDS, SOURCE_URL, api } from "@/api";
import { JobForm } from "./job-form";

describe("controlled job submission", () => {
  beforeEach(() => {
    vi.spyOn(api, "presets").mockResolvedValue({ items: [
      { id: "desk-lamp", label: "Studio Desk Lamp", source_url: SOURCE_URL },
      { id: "graph-monitor", label: "Focus Monitor", source_url: "http://fixture:8080/products/graph-monitor.html" },
    ] });
  });

  it("submits only selected fields with the owned URL and one-page budget", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(<JobForm onCreate={onCreate} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Create job" })).toBeEnabled());
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
    await waitFor(() => expect(screen.getByRole("button", { name: "Create job" })).toBeEnabled());
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
    await waitFor(() => expect(screen.getByRole("button", { name: "Create job" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Create job" }));
    const pending = screen.getByRole("button", { name: "Submitting…" });
    expect(pending).toBeDisabled();
    expect(screen.getByLabelText("Catalog preset")).toBeDisabled();
    fireEvent.click(pending);
    expect(onCreate).toHaveBeenCalledOnce();
    finish();
    await waitFor(() => expect(screen.getByRole("button", { name: "Create job" })).toBeEnabled());
  });

  it("uses the selected server preset and a new key after a failed submission changes source", async () => {
    const onCreate = vi.fn().mockRejectedValueOnce(new Error("Connection lost")).mockResolvedValue(undefined);
    render(<JobForm onCreate={onCreate} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Create job" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Create job" }));
    await screen.findByRole("alert");
    fireEvent.change(screen.getByLabelText("Catalog preset"), { target: { value: "graph-monitor" } });
    fireEvent.click(screen.getByRole("button", { name: "Create job" }));
    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(2));
    expect(onCreate.mock.calls[1][0]).toEqual({
      seed_url: "http://fixture:8080/products/graph-monitor.html", page_limit: 1, selected_fields: ALL_FIELDS,
    });
    expect(onCreate.mock.calls[1][1]).not.toBe(onCreate.mock.calls[0][1]);
  });

  it("keeps submission disabled until presets load and supports retry after a load failure", async () => {
    vi.mocked(api.presets).mockRejectedValueOnce(new Error("Presets unavailable"));
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(<JobForm onCreate={onCreate} />);
    expect(screen.getByRole("button", { name: "Create job" })).toBeDisabled();
    expect(await screen.findByRole("alert")).toHaveTextContent("Presets unavailable");
    expect(screen.getByRole("button", { name: "Create job" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Retry catalog presets" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Create job" })).toBeEnabled());
    expect(onCreate).not.toHaveBeenCalled();
  });
});
