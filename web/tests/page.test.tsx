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
    window.localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("tells the product story and remains skippable", async () => {
    render(<Home />);

    expect(await screen.findByRole("heading", { name: "Turn dangerous heat into a fundable decision" })).toBeInTheDocument();
    expect(screen.getByText("For residents")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("heading", { name: "See where heat and human need overlap" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Skip tour" }));
    expect(window.localStorage.getItem("coolspot-tour-v1")).toBe("complete");
  });

  it("loads the golden map controls and traceable evidence", async () => {
    render(<Home />);

    expect(screen.getByRole("status")).toHaveTextContent(/loading and validating/i);
    expect(await screen.findByRole("heading", { name: "Pacoima cooling investment map" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ranked recommendations" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Van Nuys / Herrick" })).toBeInTheDocument();
    expect(screen.getByLabelText("Map layer hierarchy")).toBeInTheDocument();
    expect(screen.getByLabelText("Data freshness status")).toHaveTextContent("1,991,560 FortyGuard credits remaining");
    expect(screen.getByRole("button", { name: "Refresh data" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh data" }));
    expect(screen.getByText(/Fetch recent FortyGuard evidence/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm live refresh" })).toBeDisabled();
    expect(screen.getByText(/not a temperature forecast or guaranteed outcome/i)).toBeInTheDocument();
    expect(screen.getByText("Methodology & limitations")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Interactive Pacoima heat layer map" })).toBeInTheDocument();
  });

  it("loads layers on demand and re-optimizes without a FortyGuard request", async () => {
    render(<Home />);
    await screen.findByRole("heading", { name: "Pacoima cooling investment map" });

    fireEvent.click(screen.getByRole("button", { name: "Persistence" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Persistence" })).toHaveAttribute("aria-pressed", "true"));

    fireEvent.click(screen.getByRole("button", { name: "Vulnerability" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Vulnerability" })).toHaveAttribute("aria-pressed", "true"));
    expect(screen.getByText("Higher vulnerability")).toBeInTheDocument();
    expect(screen.getByText("Lower vulnerability")).toBeInTheDocument();

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

    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));
    expect(await screen.findByText(/is selected from structured evidence/i)).toBeInTheDocument();
    expect(screen.getByText(/Deterministic fallback/)).toBeInTheDocument();
    expect(screen.getByText(/does not predict a site temperature reduction/i)).toBeInTheDocument();

    const calls = vi.mocked(fetch).mock.calls;
    expect(calls.some(([url]) => String(url).endsWith("/explanation"))).toBe(true);
    expect(calls.some(([url]) => /fortyguard/i.test(String(url)))).toBe(false);
  });

  it("bypasses the explanation cache when the user requests another explanation", async () => {
    render(<Home />);
    await screen.findByRole("heading", { name: "Pacoima cooling investment map" });

    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));
    await screen.findByText(/is selected from structured evidence/i);
    fireEvent.click(screen.getByRole("button", { name: "Refresh explanation" }));

    await waitFor(() => {
      const explanationCalls = vi.mocked(fetch).mock.calls.filter(([url]) => String(url).endsWith("/explanation"));
      expect(explanationCalls).toHaveLength(2);
      expect(JSON.parse(String(explanationCalls[1]?.[1]?.body))).toMatchObject({ regenerate: true });
    });
  });

  it("reloads every workspace dependency after a completed live refresh", async () => {
    let dataStatusCalls = 0;
    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/data-status")) {
        dataStatusCalls += 1;
        return new Response(JSON.stringify({
          ...responseFor(url, init),
          refresh_available: true,
          ...(dataStatusCalls > 1 ? { mode: "live_refreshed", heat_data_date: "2026-08-20" } : {}),
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (url.endsWith("/refresh") && init?.method === "POST") {
        return new Response(JSON.stringify({
          state: "completed",
          message: "Fresh FortyGuard heat evidence is active.",
          requested_date: "2026-08-20",
          started_at: "2026-08-21T17:30:00Z",
          completed_at: "2026-08-21T17:35:00Z",
          estimated_credit_cost: 8_440,
          credits_remaining: 1_983_120,
          hard_reserve: 500_000,
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      return new Response(JSON.stringify(responseFor(url, init)), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    render(<Home />);
    await screen.findByRole("heading", { name: "Pacoima cooling investment map" });
    fireEvent.click(screen.getByRole("button", { name: "Refresh data" }));
    fireEvent.change(screen.getByLabelText("Administrator token"), { target: { value: "admin-secret" } });
    fireEvent.submit(screen.getByRole("button", { name: "Confirm live refresh" }).closest("form")!);

    await waitFor(() => expect(screen.getByLabelText("Data freshness status")).toHaveTextContent("LIVE REFRESHED"));
    expect(screen.getByText(/map, scores, recommendations, and portfolio were recalculated/i)).toBeInTheDocument();
    const calls = vi.mocked(fetch).mock.calls;
    expect(calls.filter(([url]) => String(url).endsWith("/pilot"))).toHaveLength(2);
    expect(calls.filter(([url]) => String(url).endsWith("/candidates"))).toHaveLength(2);
    expect(calls.filter(([url]) => String(url).endsWith("/layers/heat"))).toHaveLength(2);
    expect(calls.filter(([url]) => String(url).endsWith("/optimize"))).toHaveLength(2);
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
