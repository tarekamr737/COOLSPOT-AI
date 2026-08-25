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
    await waitFor(() => expect(screen.getByRole("button", { name: "Skip tour" })).toHaveFocus());
    expect(screen.getByText("For residents")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /cooling investment journey/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("heading", { name: "See where heat and human need overlap" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /miniature map showing heat tiles/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("img", { name: /one million dollar portfolio of twenty sites/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("img", { name: /street context, price, confidence, and sources/i })).toBeInTheDocument();
    expect(screen.getByText("Evidence confidence · Site-specific")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Explore the plan" }));
    expect(window.localStorage.getItem("coolspot-tour-v1")).toBe("complete");
  });

  it("contains tour focus, closes with Escape, and restores the trigger", async () => {
    render(<Home />);

    const dialog = await screen.findByRole("dialog");
    const skip = screen.getByRole("button", { name: "Skip tour" });
    const next = screen.getByRole("button", { name: "Next" });
    next.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(skip).toHaveFocus();
    fireEvent.click(skip);

    const trigger = await screen.findByRole("button", { name: "How it works" });
    trigger.focus();
    fireEvent.click(trigger);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });

    expect(dialog).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("loads the golden map controls and traceable evidence", async () => {
    render(<Home />);

    expect(screen.getByRole("status")).toHaveTextContent(/loading and validating/i);
    const mapHeading = await screen.findByRole("heading", { name: "Pacoima cooling investment map" });
    expect(mapHeading).toBeInTheDocument();
    expect(mapHeading.closest("section")?.parentElement?.firstElementChild).toHaveAttribute("aria-labelledby", "map-title");
    expect(document.querySelector('img[src*="coolspot-logo.png"]')).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ranked recommendations" })).toBeInTheDocument();
    expect(screen.getAllByText("Selected in 4/4 planning scenarios").length).toBeGreaterThan(0);
    expect(screen.getByText("Scenario stability only, not statistical confidence.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Van Nuys / Herrick" })).toBeInTheDocument();
    expect(screen.getByLabelText("Map layer hierarchy")).toBeInTheDocument();
    expect(screen.getByLabelText("Data freshness status")).toHaveTextContent("1,991,560 FortyGuard credits remaining");
    expect(screen.getByRole("button", { name: "Refresh data" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh data" }));
    expect(screen.getByText(/Fetch recent FortyGuard evidence/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm live refresh" })).toBeDisabled();
    expect(screen.getByText(/not a temperature forecast or guaranteed outcome/i)).toBeInTheDocument();
    expect(screen.getByText("Planning assumption")).toBeInTheDocument();
    expect(screen.getByText("Modeled")).toBeInTheDocument();
    expect(screen.getByText("Verified evidence")).toBeInTheDocument();
    expect(screen.getByText("Field verification required")).toBeInTheDocument();
    expect(screen.getByText("Derived screening scores")).toBeInTheDocument();
    expect(screen.getByText("Observed and published evidence")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Observed inputs and derivation" })).toBeInTheDocument();
    expect(screen.getByText("43.5%")).toBeInTheDocument();
    expect(screen.getByText("Street context confidence").nextElementSibling).toHaveTextContent("0.792");
    expect(screen.getByText("Shade opportunity screen").nextElementSibling).toHaveTextContent("0.565");
    expect(screen.getByLabelText("Decision screening factors")).toHaveTextContent("Scenario priority");
    expect(screen.getByLabelText("Decision screening factors")).toHaveTextContent("Intervention evidence");
    expect(screen.getByLabelText("Decision screening factors")).toHaveTextContent("Feasibility");
    expect(screen.getByLabelText("Decision screening factors")).toHaveTextContent("Scenario robustness");
    fireEvent.click(screen.getByRole("button", { name: "View street images" }));
    expect(await screen.findByRole("button", { name: "Street image" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Segmentation" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText(/does not prove all-day shade/i)).toBeInTheDocument();
    expect(screen.getAllByText("Historical exceedance")).toHaveLength(2);
    expect(screen.getByText(/6.89 hours above 30 °C/)).toBeInTheDocument();
    expect(screen.getByText("Peak heat observed around")).toBeInTheDocument();
    expect(screen.getByText(/15:00 UTC/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Weather conditions at this finalist" })).toBeInTheDocument();
    expect(screen.getByText(/Source complete · 3 of 3/)).toBeInTheDocument();
    expect(screen.getByText("Apparent temperature").nextElementSibling).toHaveTextContent("35.30 °C");
    expect(screen.getByText("Relative humidity").nextElementSibling).toHaveTextContent("24.3%");
    expect(screen.getByText("Clear-sky GHI").nextElementSibling).toHaveTextContent("779.49 vendor value");
    expect(screen.getAllByRole("link", { name: "FortyGuard source" }).some((link) => link.getAttribute("href") === "https://docs-api.fortyguard.com/docs/environmental-parameters")).toBe(true);
    expect(screen.getByText(/does not establish medical risk/i)).toBeInTheDocument();
    expect(screen.getByText("Methodology & limitations")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Methodology & limitations"));
    expect(screen.getByRole("heading", { name: "Heat evidence provenance" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "FortyGuard Heatmap API" })).toBeInTheDocument();
    expect(screen.getByText(/not contemporaneous with active heat evidence/i)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Interactive Pacoima heat layer map" })).toBeInTheDocument();
  });

  it("shows a truthful empty state when exact-site street context is unavailable", async () => {
    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const fixtureUrl = url.endsWith("/street-view") ? url.replace("site-0", "site-1") : url;
      return new Response(JSON.stringify(responseFor(fixtureUrl, init)), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    render(<Home />);

    await screen.findByRole("heading", { name: "Pacoima cooling investment map" });
    fireEvent.click(screen.getByRole("button", { name: "View street images" }));

    expect(await screen.findByText("No verified segmentation for this site")).toBeInTheDocument();
    expect(screen.getByText("No verified street segmentation is cached for this site.")).toBeInTheDocument();
  });

  it("exposes an initial load failure and recovers through Retry", async () => {
    let pilotCalls = 0;
    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/pilot") && pilotCalls++ === 0) {
        return new Response(JSON.stringify({ detail: "Cached pilot data is unavailable." }), {
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

    expect(await screen.findByRole("alert")).toHaveTextContent("Cached pilot data is unavailable.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByRole("heading", { name: "Pacoima cooling investment map" })).toBeInTheDocument();
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
    await waitFor(() => expect(screen.getByText("20 sites · 0 FortyGuard credits")).toBeInTheDocument());

    const calls = vi.mocked(fetch).mock.calls;
    expect(calls.some(([url]) => String(url).endsWith("/layers/persistence"))).toBe(true);
    expect(calls.some(([url, init]) => String(url).endsWith("/optimize") && String(init?.body).includes("1000000"))).toBe(true);
    expect(calls.some(([url]) => /fortyguard/i.test(String(url)))).toBe(false);
  });

  it("changes planning priorities at zero vendor cost", async () => {
    render(<Home />);
    await screen.findByRole("heading", { name: "Pacoima cooling investment map" });
    fireEvent.click(screen.getByRole("button", { name: "Skip tour" }));

    fireEvent.change(screen.getByLabelText("Planning priority"), {
      target: { value: "exposure_first" },
    });

    await waitFor(() => {
      expect(screen.getByLabelText("Planning priority")).toHaveValue("exposure_first");
      expect(screen.getByText("H 30 · E 40 · V 20 · O 10")).toBeInTheDocument();
    });
    const calls = vi.mocked(fetch).mock.calls;
    expect(calls.some(([url, init]) =>
      String(url).endsWith("/optimize")
      && String(init?.body).includes('"scoring_preset":"exposure_first"'),
    )).toBe(true);
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
