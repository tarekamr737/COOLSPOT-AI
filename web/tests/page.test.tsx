import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Home from "@/app/page";
import { responseFor } from "./api-fixtures";

describe("Home", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
        new Response(JSON.stringify(responseFor(String(input), init)), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("loads the golden map controls and traceable evidence", async () => {
    render(<Home />);

    expect(screen.getByRole("status")).toHaveTextContent(/loading and validating/i);
    expect(await screen.findByRole("heading", { name: "Pacoima cooling investment map" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ranked recommendations" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Van Nuys / Herrick" })).toBeInTheDocument();
    expect(screen.getByLabelText("Map layer hierarchy")).toBeInTheDocument();
    expect(screen.getByLabelText("Cached data status")).toHaveTextContent("1,991,560 FortyGuard credits remaining");
    expect(screen.getByText(/not a temperature forecast or guaranteed outcome/i)).toBeInTheDocument();
    expect(screen.getByText("Methodology & limitations")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Interactive Pacoima heat layer map" })).toBeInTheDocument();
  });

  it("loads layers on demand and re-optimizes without a FortyGuard request", async () => {
    render(<Home />);
    await screen.findByRole("heading", { name: "Pacoima cooling investment map" });

    fireEvent.click(screen.getByRole("button", { name: "Persistence" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Persistence" })).toHaveAttribute("aria-pressed", "true"));

    fireEvent.click(screen.getByRole("button", { name: "$1M" }));
    await screen.findByRole("heading", { name: "$1,000,000 budget" });
    await waitFor(() => expect(screen.getByText("20 sites · zero vendor calls")).toBeInTheDocument());

    const calls = vi.mocked(fetch).mock.calls;
    expect(calls.some(([url]) => String(url).endsWith("/layers/persistence"))).toBe(true);
    expect(calls.some(([url, init]) => String(url).endsWith("/optimize") && String(init?.body).includes("1000000"))).toBe(true);
    expect(calls.some(([url]) => /fortyguard/i.test(String(url)))).toBe(false);
  });

  it("generates a deterministic explanation from the selected evidence", async () => {
    render(<Home />);
    await screen.findByRole("heading", { name: "Pacoima cooling investment map" });

    fireEvent.click(screen.getByRole("button", { name: "Explain" }));
    expect(await screen.findByText(/is selected from structured evidence/i)).toBeInTheDocument();
    expect(screen.getByText("Deterministic template · structured evidence only")).toBeInTheDocument();
    expect(screen.getByText(/does not predict a site temperature reduction/i)).toBeInTheDocument();

    const calls = vi.mocked(fetch).mock.calls;
    expect(calls.some(([url]) => String(url).endsWith("/explanation"))).toBe(true);
    expect(calls.some(([url]) => /fortyguard/i.test(String(url)))).toBe(false);
  });

  it("preserves the workspace and previous layer when an update fails", async () => {
    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/layers/persistence")) {
        return new Response(JSON.stringify({ detail: "Cached persistence data is unavailable." }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify(responseFor(url, init)), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    render(<Home />);
    await screen.findByRole("heading", { name: "Pacoima cooling investment map" });
    fireEvent.click(screen.getByRole("button", { name: "Persistence" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Cached persistence data is unavailable. The previous layer remains visible.",
    );
    expect(screen.getByRole("button", { name: "Heat" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("heading", { name: "Ranked recommendations" })).toBeInTheDocument();
  });
});
