"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getCandidates, getDataStatus, getExplanation, getLayer, getMethodology, getPilot, getRefreshStatus, getSite, optimize, startRefresh } from "@/lib/api-client";
import { layerNames, type Candidate, type CandidateList, type DataStatus, type Explanation, type LayerName, type LayerResponse, type Methodology, type Pilot, type Portfolio, type RefreshStatus, type Site } from "@/lib/api-schemas";
import { MapView } from "./map-view";
import styles from "./planning-shell.module.css";

type WorkspaceData = { pilot: Pilot; candidates: CandidateList; status: DataStatus; methodology: Methodology; portfolio: Portfolio; site: Site };
const layerLabels: Record<LayerName, string> = { heat: "Heat", persistence: "Persistence", exposure: "Exposure", vulnerability: "Vulnerability" };
const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

function compactCurrency(value: number) {
  return value >= 1_000_000 ? `$${value / 1_000_000}M` : `$${Math.round(value / 1_000)}k`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
}

function impact(candidate: Candidate) {
  return candidate.benefit_score * candidate.feasibility_score * candidate.confidence;
}

function interventionLabel(value: Candidate["intervention_type"]) {
  return value.split("_").map((word) => word[0]?.toUpperCase() + word.slice(1)).join(" ");
}

function BrandMark() {
  return <svg aria-hidden="true" className={styles.brandMark} viewBox="0 0 32 32"><path d="M4 16a12 12 0 0 1 19.4-9.45L16 16Z" /><path d="M28 16a12 12 0 0 1-19.4 9.45L16 16Z" /><circle cx="16" cy="16" r="3.5" /></svg>;
}

function latestCompleteDate() {
  const value = new Date();
  value.setUTCDate(value.getUTCDate() - 1);
  return value.toISOString().slice(0, 10);
}

function RefreshControl({ available, onCompleted }: { available: boolean; onCompleted: () => Promise<void> }) {
  const [expanded, setExpanded] = useState(false);
  const [token, setToken] = useState("");
  const [analysisDate, setAnalysisDate] = useState(latestCompleteDate);
  const [status, setStatus] = useState<RefreshStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const completionHandled = useRef(false);

  useEffect(() => {
    if (status?.state !== "running") return;
    const timer = window.setInterval(() => {
      void getRefreshStatus().then(setStatus).catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [status?.state]);

  useEffect(() => {
    if (status?.state !== "completed" || completionHandled.current) return;
    completionHandled.current = true;
    setToken("");
    void onCompleted();
  }, [onCompleted, status?.state]);

  const submit = async () => {
    setError(null);
    completionHandled.current = false;
    try {
      setStatus(await startRefresh(analysisDate, token));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to start the live refresh.");
    }
  };

  return <div className={styles.refreshControl}>
    <button aria-expanded={expanded} className={styles.refreshTrigger} onClick={() => setExpanded((value) => !value)} type="button">Refresh data</button>
    {expanded ? <form className={styles.refreshPanel} onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <div><strong>Fetch recent FortyGuard evidence</strong><p>This submits two paid heatmap jobs, TCM and persistence. The 500,000-credit reserve is enforced server-side.</p></div>
      <label>Analysis date<input max={latestCompleteDate()} onChange={(event) => setAnalysisDate(event.currentTarget.value)} required type="date" value={analysisDate} /></label>
      <label>Administrator token<input autoComplete="off" onChange={(event) => setToken(event.currentTarget.value)} required type="password" value={token} /></label>
      {!available ? <p className={styles.refreshWarning}>Server refresh is not enabled yet. Configure live mode and an administrator token.</p> : null}
      {status ? <p aria-live="polite" className={styles.refreshMessage}>{status.message}{status.estimated_credit_cost ? ` Estimated cost: ${status.estimated_credit_cost.toLocaleString()} credits.` : ""}</p> : null}
      {error ? <p className={styles.refreshError} role="alert">{error}</p> : null}
      <div className={styles.refreshActions}><button onClick={() => setExpanded(false)} type="button">Cancel</button><button disabled={!available || !token || status?.state === "running"} type="submit">{status?.state === "running" ? "Refreshing…" : "Confirm live refresh"}</button></div>
    </form> : null}
  </div>;
}

function TopBar({ pilot, status, onRefreshComplete }: Pick<WorkspaceData, "pilot" | "status"> & { onRefreshComplete: () => Promise<void> }) {
  const live = status.mode === "live_refreshed";
  return <header className={styles.topBar}>
    <div className={styles.brandLockup}><BrandMark /><div><p className={styles.brandName}>COOLSPOT AI</p><p className={styles.brandDescriptor}>Cooling investment planner</p></div></div>
    <div className={styles.pilotIdentity}><span className={styles.eyebrow}>Pilot area</span><span className={styles.pilotName}>{pilot.name}</span><span className={styles.areaTag}>{pilot.area_sq_mi.toFixed(3)} mi²</span></div>
    <div className={styles.dataActions}><div className={styles.dataStatus} aria-label="Data freshness status"><div className={`${styles.statusLine} ${live ? styles.liveStatus : ""}`}><span aria-hidden="true" className={styles.statusDot} /><span>{live ? "LIVE REFRESHED" : "CACHED ANALYSIS"}</span><time dateTime={status.heat_data_date}>{formatDate(status.heat_data_date)}</time></div><p>{status.credits.remaining.toLocaleString()} FortyGuard credits remaining</p></div><RefreshControl available={status.refresh_available} onCompleted={onRefreshComplete} /></div>
  </header>;
}

type RecommendationRailProps = { candidates: Candidate[]; portfolio: Portfolio; activeCandidateId: string; onSelect: (candidate: Candidate) => void };

function RecommendationRail({ candidates, portfolio, activeCandidateId, onSelect }: RecommendationRailProps) {
  return <aside className={styles.recommendationRail} aria-labelledby="recommendations-title">
    <div className={styles.railHeading}><div><p className={styles.eyebrow}>Optimized portfolio</p><h2 id="recommendations-title">Ranked recommendations</h2></div><span className={styles.countBadge}>{portfolio.selected_count} sites</span></div>
    <div className={styles.portfolioSummary} aria-label="Portfolio summary"><div><span>Budget allocated</span><strong>{compactCurrency(portfolio.total_cost_usd)}</strong></div><div><span>Modeled impact</span><strong>{portfolio.total_modeled_impact_score.toFixed(3)}</strong></div><div><span>Replan credits</span><strong>0</strong></div></div>
    <ol className={styles.recommendationList}>{candidates.map((candidate, index) => <li className={styles.recommendation} key={candidate.id}>
      <button aria-current={candidate.id === activeCandidateId ? "true" : undefined} className={styles.recommendationButton} onClick={() => onSelect(candidate)} type="button">
        <span className={styles.rank}>{String(index + 1).padStart(2, "0")}</span><span className={styles.recommendationBody}><span className={styles.interventionLabel}>{interventionLabel(candidate.intervention_type)}</span><strong>{candidate.site_name}</strong><span className={styles.recommendationMeta}><span>{compactCurrency(candidate.planning_cost_usd)} planning cost</span><span>{impact(candidate).toFixed(3)} impact</span></span></span>
      </button>
    </li>)}</ol>
  </aside>;
}

type BudgetBarProps = { budget: number; portfolio: Portfolio; methodology: Methodology; optimizing: boolean; onCommit: (budget: number) => void; onPreview: (budget: number) => void };

function BudgetBar({ budget, portfolio, methodology, optimizing, onCommit, onPreview }: BudgetBarProps) {
  const { optimization } = methodology;
  return <section className={styles.budgetBar} aria-labelledby="budget-title">
    <div><p className={styles.eyebrow}>Investment scenario</p><h2 id="budget-title">{currency.format(budget)} budget</h2></div>
    <div className={styles.budgetControl}><div className={styles.budgetScale} aria-label="Budget presets">{optimization.budget_presets_usd.map((preset) => <button aria-pressed={budget === preset} className={budget === preset ? styles.activeBudget : undefined} disabled={optimizing} key={preset} onClick={() => onCommit(preset)} type="button">{compactCurrency(preset)}</button>)}</div>
      <label className={styles.sliderLabel}><span className="sr-only">Custom budget</span><input aria-valuetext={currency.format(budget)} disabled={optimizing} max={optimization.custom_budget_max_usd} min={optimization.custom_budget_min_usd} onChange={(event) => onPreview(Number(event.currentTarget.value))} onKeyUp={(event) => onCommit(Number(event.currentTarget.value))} onPointerUp={(event) => onCommit(Number(event.currentTarget.value))} step={50_000} type="range" value={budget} /></label>
    </div>
    <p aria-live="polite" className={styles.budgetNote}>{optimizing ? "Re-optimizing…" : `${portfolio.selected_count} sites · zero vendor calls`}</p>
  </section>;
}

type MapWorkspaceProps = { budget: number; data: WorkspaceData; layer: LayerResponse; activeLayer: LayerName; layerLoading: boolean; optimizing: boolean; activeCandidateId: string; onBudgetCommit: (budget: number) => void; onBudgetPreview: (budget: number) => void; onLayerChange: (layer: LayerName) => void; onSelectSite: (siteId: string) => void };

function MapWorkspace({ budget, data, layer, activeLayer, layerLoading, optimizing, activeCandidateId, onBudgetCommit, onBudgetPreview, onLayerChange, onSelectSite }: MapWorkspaceProps) {
  return <section className={styles.mapWorkspace} aria-labelledby="map-title">
    <BudgetBar budget={budget} methodology={data.methodology} onCommit={onBudgetCommit} onPreview={onBudgetPreview} optimizing={optimizing} portfolio={data.portfolio} />
    <div className={styles.mapCanvas}><h1 className="sr-only" id="map-title">Pacoima cooling investment map</h1><MapView activeCandidateId={activeCandidateId} candidates={data.candidates.candidates} layer={layer} onSelectSite={onSelectSite} pilot={data.pilot} selectedCandidateIds={data.portfolio.selected_candidate_ids} />
      <div className={styles.heatLegend} aria-label={`${layerLabels[activeLayer]} score legend`}><span>HIGHER</span><div className={`${styles.legendRamp} ${styles[`${activeLayer}Ramp`]}`} aria-hidden="true"><i /><i /><i /><i /></div><span>LOWER</span></div>
    </div>
    <nav className={styles.layerDock} aria-label="Map layer hierarchy"><span className={styles.eyebrow}>Layers</span><ul>{layerNames.map((name) => <li key={name}><button aria-pressed={activeLayer === name} className={activeLayer === name ? styles.activeLayer : undefined} disabled={layerLoading} onClick={() => onLayerChange(name)} type="button"><span className={styles.layerSwatch} aria-hidden="true" />{layerLabels[name]}</button></li>)}</ul><span aria-live="polite" className={styles.layerState}>{layerLoading ? "Loading layer…" : `${layer.features.length.toLocaleString()} tiles`}</span></nav>
  </section>;
}

type EvidencePanelProps = { candidate: Candidate; site: Site; methodology: Methodology; explanationMode: DataStatus["explanation_mode"]; siteLoading: boolean; explanation?: Explanation; explanationLoading: boolean; explanationError: string | null; onExplain: () => void };

function EvidencePanel({ candidate, site, methodology, explanationMode, siteLoading, explanation, explanationLoading, explanationError, onExplain }: EvidencePanelProps) {
  const option = site.options.find((item) => item.candidate.id === candidate.id) ?? site.options[0];
  const { tile, intervention } = option;
  const sourceIds = new Set([...intervention.planning_cost.source_ids, ...intervention.benefit_evidence.source_ids]);
  const sources = methodology.interventions.sources.filter((source) => sourceIds.has(source.id));
  return <aside aria-busy={siteLoading} className={styles.evidencePanel} aria-labelledby="evidence-title">
    <div className={styles.evidenceHeader}><div><p className={styles.eyebrow}>Site evidence · Tile {candidate.tile_id}</p><h2 id="evidence-title">{site.site_name}</h2></div><span className={styles.selectedBadge}>{siteLoading ? "Loading" : "Selected"}</span></div>
    <div className={styles.interventionCallout}><p>Recommended intervention</p><h3>{intervention.label}</h3><div><span>{currency.format(intervention.planning_cost.estimate_usd)} planning cost</span><span>{compactCurrency(intervention.planning_cost.low_usd)}–{compactCurrency(intervention.planning_cost.high_usd)} range</span></div></div>
    <section className={styles.impactSection}><div><p className={styles.eyebrow}>Modeled impact score</p><strong>{impact(candidate).toFixed(3)}</strong></div><p>Relative planning score from cached evidence and screening assumptions. It is not a temperature forecast or guaranteed outcome.</p></section>
    <dl className={styles.evidenceList}><div><dt>Observed heat</dt><dd>{tile.heat.average_temperature_c.toFixed(2)} °C tile average</dd></div><div><dt>Heat persistence</dt><dd>{tile.heat.persistence_hours.toFixed(2)} hours</dd></div><div><dt>Published patronage activity</dt><dd>{tile.exposure.published_patronage_activity?.toFixed(2) ?? "Not available"}</dd></div><div><dt>Vulnerability context</dt><dd>{tile.scores.vulnerability.toFixed(3)} modeled score</dd></div></dl>
    <details className={styles.scoreBreakdown}><summary>How the priority score is calculated</summary><dl>{Object.entries(tile.scores).map(([name, value]) => <div key={name}><dt>{name.replaceAll("_", " ")}</dt><dd>{value.toFixed(3)}{methodology.scoring.priority_weights[name] !== undefined ? ` · ${(methodology.scoring.priority_weights[name] * 100).toFixed(0)}% weight` : ""}</dd></div>)}</dl><p>Observed and published inputs are normalized to 0–1, then combined with the published weights. The intervention impact also applies feasibility and confidence screening.</p></details>
    <section className={styles.confidenceSection}><div className={styles.confidenceHeading}><span>Evidence confidence</span><strong>Unverified screening · {candidate.confidence.toFixed(1)}</strong></div><div className={styles.confidenceTrack} aria-label={`Confidence score ${candidate.confidence} out of 1`}><span style={{ width: `${candidate.confidence * 100}%` }} /></div><p>{intervention.uncertainty.summary}</p></section>
    <section className={styles.explanationSection} aria-labelledby="explanation-title"><div className={styles.explanationHeading}><div><p className={styles.eyebrow}>AI evidence assistant</p><h3 id="explanation-title">Why this site?</h3></div><button disabled={explanationLoading || siteLoading} onClick={onExplain} type="button">{explanationLoading ? "Explaining…" : explanation ? "Regenerate" : "Ask AI"}</button></div><p className={styles.aiBoundary}>The AI explains the selected result. It never ranks sites or adds evidence.</p>{explanationError ? <p className={styles.explanationError} role="alert">{explanationError}</p> : null}{explanation ? <div className={styles.explanationBody}><p>{explanation.summary}</p><h4>Evidence used</h4><ul>{explanation.why_selected.map((reason) => <li key={reason}>{reason}</li>)}</ul><h4>Limits</h4><ul>{explanation.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul><p className={styles.templateLabel}>{explanation.mode === "openrouter" ? `Gemma via OpenRouter · grounded evidence only` : "Deterministic fallback · configure OpenRouter to enable AI wording"}</p></div> : <p className={styles.explanationPrompt}>{explanationMode === "openrouter" ? "Gemma will explain only the verified facts shown for this site." : "The grounded fallback is ready; configure OpenRouter to enable Gemma wording."}</p>}</section>
    <details className={styles.methodology} id="methodology"><summary>Methodology & limitations</summary><div className={styles.methodologyBody}><p>{methodology.optimization.objective_note}</p><p>{methodology.interventions.cost_basis.disclaimer}</p><ul>{candidate.evidence.map((evidence) => <li key={evidence.kind}><strong>{evidence.kind.replaceAll("_", " ")}</strong><span>{evidence.statement}</span></li>)}</ul><h3>Source links</h3><ul className={styles.sourceList}>{sources.map((source) => <li key={source.id}><a href={source.url} rel="noreferrer" target="_blank">{source.publisher}: {source.title}</a><span>Retrieved {formatDate(source.retrieved_at)}</span></li>)}</ul><h3>Pilot limitations</h3><ul>{methodology.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></div></details>
  </aside>;
}

function LoadingShell() {
  return <main className={styles.loadingShell} aria-busy="true"><header className={styles.loadingHeader}><BrandMark /><span className={styles.loadingLine} /></header><div className={styles.loadingWorkspace}><div /><div /><div /></div><p className={styles.loadingAnnouncement} role="status">Loading and validating cached Pacoima evidence.</p></main>;
}

async function fetchWorkspace() {
  const pilotPromise = getPilot();
  const candidatesPromise = getCandidates();
  const statusPromise = getDataStatus();
  const methodologyPromise = getMethodology();
  const heatPromise = getLayer("heat");
  const pilot = await pilotPromise;
  const [candidates, status, methodology, heat, portfolio] = await Promise.all([
    candidatesPromise,
    statusPromise,
    methodologyPromise,
    heatPromise,
    optimize(pilot.default_budget_usd),
  ]);
  const byId = new Map(candidates.candidates.map((candidate) => [candidate.id, candidate]));
  const first = portfolio.selected_candidate_ids
    .map((id) => byId.get(id))
    .filter((candidate): candidate is Candidate => Boolean(candidate))
    .sort((a, b) => impact(b) - impact(a) || a.id.localeCompare(b.id))[0];
  if (!first) throw new Error("The optimized portfolio contains no known candidates.");
  const site = await getSite(first.site_id);
  return {
    data: { pilot, candidates, status, methodology, portfolio, site },
    heat,
    activeCandidateId: first.id,
  };
}

export function PlanningShell() {
  const [data, setData] = useState<WorkspaceData | null>(null);
  const [layers, setLayers] = useState<Partial<Record<LayerName, LayerResponse>>>({});
  const [activeLayer, setActiveLayer] = useState<LayerName>("heat");
  const [activeCandidateId, setActiveCandidateId] = useState("");
  const [budget, setBudget] = useState(500_000);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [optimizing, setOptimizing] = useState(false);
  const [layerLoading, setLayerLoading] = useState(false);
  const [siteLoading, setSiteLoading] = useState(false);
  const [explanations, setExplanations] = useState<Record<string, Explanation>>({});
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [explanationError, setExplanationError] = useState<string | null>(null);
  const requestSequence = useRef(0);

  const applyWorkspace = useCallback((loaded: Awaited<ReturnType<typeof fetchWorkspace>>) => {
    setFatalError(null);
    setBudget(loaded.data.pilot.default_budget_usd);
    setActiveCandidateId(loaded.activeCandidateId);
    setLayers({ heat: loaded.heat });
    setData(loaded.data);
  }, []);

  useEffect(() => {
    let active = true;
    void fetchWorkspace().then((loaded) => {
      if (active) applyWorkspace(loaded);
    }).catch((caught: unknown) => {
      if (active) setFatalError(caught instanceof Error ? caught.message : "Unable to load COOLSPOT data.");
    });
    return () => { active = false; };
  }, [applyWorkspace]);

  const retry = useCallback(async () => {
    try { applyWorkspace(await fetchWorkspace()); }
    catch (caught) { setFatalError(caught instanceof Error ? caught.message : "Unable to load COOLSPOT data."); }
  }, [applyWorkspace]);

  const recommendations = useMemo(() => {
    if (!data) return [];
    const selected = new Set(data.portfolio.selected_candidate_ids);
    return data.candidates.candidates.filter((candidate) => selected.has(candidate.id)).sort((a, b) => impact(b) - impact(a) || a.id.localeCompare(b.id));
  }, [data]);

  const selectCandidate = useCallback(async (candidate: Candidate) => {
    if (!data || candidate.id === activeCandidateId) return;
    setSiteLoading(true); setOperationError(null); setExplanationError(null);
    try { const site = await getSite(candidate.site_id); setActiveCandidateId(candidate.id); setData((current) => current ? { ...current, site } : current); }
    catch (caught) { setOperationError(`${caught instanceof Error ? caught.message : "Unable to load site evidence."} The previous site remains selected.`); }
    finally { setSiteLoading(false); }
  }, [activeCandidateId, data]);

  const selectSite = useCallback((siteId: string) => {
    const candidate = recommendations.find((item) => item.site_id === siteId);
    if (candidate) void selectCandidate(candidate);
  }, [recommendations, selectCandidate]);

  const changeBudget = useCallback(async (nextBudget: number) => {
    if (!data || nextBudget === data.portfolio.budget_usd || optimizing) return;
    const sequence = ++requestSequence.current; setBudget(nextBudget); setOptimizing(true); setOperationError(null); setExplanationError(null);
    try {
      const portfolio = await optimize(nextBudget);
      if (sequence !== requestSequence.current) return;
      const byId = new Map(data.candidates.candidates.map((candidate) => [candidate.id, candidate]));
      const ranked = portfolio.selected_candidate_ids.map((id) => byId.get(id)).filter((candidate): candidate is Candidate => Boolean(candidate)).sort((a, b) => impact(b) - impact(a) || a.id.localeCompare(b.id));
      const currentIsSelected = portfolio.selected_candidate_ids.includes(activeCandidateId);
      const next = currentIsSelected ? byId.get(activeCandidateId) : ranked[0];
      if (!next) throw new Error("The optimized portfolio contains no known candidates.");
      const site = currentIsSelected ? data.site : await getSite(next.site_id);
      setActiveCandidateId(next.id); setData((current) => current ? { ...current, portfolio, site } : current);
    } catch (caught) { setBudget(data.portfolio.budget_usd); setOperationError(`${caught instanceof Error ? caught.message : "Unable to optimize this budget."} The previous portfolio remains active.`); }
    finally { if (sequence === requestSequence.current) setOptimizing(false); }
  }, [activeCandidateId, data, optimizing]);

  const changeLayer = useCallback(async (nextLayer: LayerName) => {
    if (nextLayer === activeLayer || layerLoading) return;
    const cached = layers[nextLayer];
    if (cached) { setActiveLayer(nextLayer); return; }
    setLayerLoading(true); setOperationError(null);
    try { const response = await getLayer(nextLayer); setLayers((current) => ({ ...current, [nextLayer]: response })); setActiveLayer(nextLayer); }
    catch (caught) { setOperationError(`${caught instanceof Error ? caught.message : "Unable to load this map layer."} The previous layer remains visible.`); }
    finally { setLayerLoading(false); }
  }, [activeLayer, layerLoading, layers]);

  const requestExplanation = useCallback(async (candidate: Candidate) => {
    if (!data || explanationLoading) return;
    const explanationKey = `${candidate.id}:${data.portfolio.budget_usd}`;
    setExplanationLoading(true); setExplanationError(null);
    try {
      const explanation = await getExplanation(candidate.site_id, candidate.id, data.portfolio.budget_usd);
      setExplanations((current) => ({ ...current, [explanationKey]: explanation }));
    } catch (caught) {
      setExplanationError(caught instanceof Error ? caught.message : "Unable to explain this site.");
    } finally {
      setExplanationLoading(false);
    }
  }, [data, explanationLoading]);

  if (fatalError) return <main className={styles.statePage} role="alert"><BrandMark /><p className={styles.eyebrow}>Data unavailable</p><h1>COOLSPOT could not load the cached analysis</h1><p>{fatalError}</p><button onClick={() => void retry()} type="button">Retry</button></main>;
  if (!data || !layers[activeLayer]) return <LoadingShell />;
  const activeCandidate = data.candidates.candidates.find((candidate) => candidate.id === activeCandidateId) ?? recommendations[0];
  if (!activeCandidate) return <LoadingShell />;
  const explanationKey = `${activeCandidate.id}:${data.portfolio.budget_usd}`;

  return <div className={styles.appShell}><a className={styles.skipLink} href="#map-title">Skip to map workspace</a><TopBar onRefreshComplete={retry} pilot={data.pilot} status={data.status} />{operationError ? <div className={styles.operationError} role="alert"><span>{operationError}</span><button aria-label="Dismiss error" onClick={() => setOperationError(null)} type="button">Dismiss</button></div> : null}<main className={styles.workspace}>
    <RecommendationRail activeCandidateId={activeCandidate.id} candidates={recommendations} onSelect={(candidate) => void selectCandidate(candidate)} portfolio={data.portfolio} />
    <MapWorkspace activeCandidateId={activeCandidate.id} activeLayer={activeLayer} budget={budget} data={data} layer={layers[activeLayer]} layerLoading={layerLoading} onBudgetCommit={(value) => void changeBudget(value)} onBudgetPreview={setBudget} onLayerChange={(name) => void changeLayer(name)} onSelectSite={selectSite} optimizing={optimizing} />
    <EvidencePanel candidate={activeCandidate} explanation={explanations[explanationKey]} explanationError={explanationError} explanationLoading={explanationLoading} explanationMode={data.status.explanation_mode} methodology={data.methodology} onExplain={() => void requestExplanation(activeCandidate)} site={data.site} siteLoading={siteLoading} />
  </main></div>;
}
