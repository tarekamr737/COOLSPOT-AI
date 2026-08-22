"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import { getCandidates, getDataStatus, getExplanation, getLayer, getMethodology, getPilot, getRefreshStatus, getSite, getStreetView, optimize, startRefresh } from "@/lib/api-client";
import { layerNames, type Candidate, type CandidateList, type DataStatus, type Explanation, type LayerName, type LayerResponse, type Methodology, type Pilot, type Portfolio, type RefreshStatus, type Site, type StreetViewContext } from "@/lib/api-schemas";
import { MapView } from "./map-view";
import styles from "./planning-shell.module.css";

type WorkspaceData = { pilot: Pilot; candidates: CandidateList; status: DataStatus; methodology: Methodology; portfolio: Portfolio; site: Site };
const layerLabels: Record<LayerName, string> = { heat: "Heat", persistence: "Persistence", exposure: "Exposure", vulnerability: "Vulnerability" };
const legendEndpoints: Record<LayerName, readonly [string, string]> = {
  heat: ["Higher", "Lower"],
  persistence: ["Higher", "Lower"],
  exposure: ["Higher", "Lower"],
  vulnerability: ["Higher vulnerability", "Lower vulnerability"],
};
const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const coreEvidenceSources = [
  { label: "FortyGuard: Heatmap Generation", url: "https://docs-api.fortyguard.com/docs/create-heatmap" },
  { label: "LA Metro: Bus Stop Hub", url: "https://busstophub.metro.net/resources/maps/" },
  { label: "U.S. Census: 2024 ACS 5-year data", url: "https://www.census.gov/programs-surveys/acs/data/summary-file.2024.html" },
] as const;

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
  const [reloading, setReloading] = useState(false);
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
    setReloading(true);
    void onCompleted().then(() => {
      setStatus((current) => current?.state === "completed" ? {
        ...current,
        message: "Fresh evidence is active. The map, scores, recommendations, and portfolio were recalculated.",
      } : current);
    }).catch((caught: unknown) => {
      setError(`${caught instanceof Error ? caught.message : "Unable to reload the workspace."} The refresh completed, but the app could not load its new outputs.`);
    }).finally(() => setReloading(false));
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
      <div className={styles.refreshActions}><button onClick={() => setExpanded(false)} type="button">Cancel</button><button disabled={!available || !token || status?.state === "running" || reloading} type="submit">{status?.state === "running" ? "Refreshing…" : reloading ? "Updating app…" : "Confirm live refresh"}</button></div>
    </form> : null}
  </div>;
}

function TopBar({ pilot, status, onRefreshComplete, onTour }: Pick<WorkspaceData, "pilot" | "status"> & { onRefreshComplete: () => Promise<void>; onTour: () => void }) {
  const live = status.mode === "live_refreshed";
  return <header className={styles.topBar}>
    <div className={styles.brandLockup}><BrandMark /><div><p className={styles.brandName}>COOLSPOT AI</p><p className={styles.brandDescriptor}>Cooling investment planner</p></div></div>
    <div className={styles.pilotIdentity}><span className={styles.eyebrow}>Pilot area</span><span className={styles.pilotName}>{pilot.name}</span><span className={styles.areaTag}>{pilot.area_sq_mi.toFixed(3)} mi²</span></div>
    <div className={styles.dataActions}><button className={styles.tourTrigger} onClick={onTour} type="button">How it works</button><div className={styles.dataStatus} aria-label="Data freshness status"><div className={`${styles.statusLine} ${live ? styles.liveStatus : ""}`}><span aria-hidden="true" className={styles.statusDot} /><span>{live ? "LIVE REFRESHED" : "CACHED ANALYSIS"}</span><time dateTime={status.heat_data_date}>{formatDate(status.heat_data_date)}</time></div><p>{status.credits.remaining.toLocaleString()} FortyGuard credits remaining</p></div><RefreshControl available={status.refresh_available} onCompleted={onRefreshComplete} /></div>
  </header>;
}

const tourSteps = [
  { label: "The public need", title: "Turn dangerous heat into a fundable decision", body: "Residents gain safer public places, investors see a transparent project pipeline, and government teams can defend where limited cooling dollars go first." },
  { label: "The evidence", title: "See where heat and human need overlap", body: "The map combines cached FortyGuard heat and persistence with published transit activity, public destinations, and Census vulnerability context. Every layer keeps its date and limitations." },
  { label: "The investment", title: "Test a budget before spending it", body: "Change the budget and the deterministic optimizer rebuilds a feasible portfolio instantly. It makes zero new vendor calls and never asks AI to rank sites." },
  { label: "The audit", title: "Inspect the place, price, sources, and uncertainty", body: "Select a recommendation to review its local planning allowance, real street segmentation where cached, grounded AI explanation, source links, and required field checks." },
] as const;

function TourVisual({ step }: { step: number }) {
  if (step === 0) {
    return <div aria-label="Cooling investment journey from public need to accountable action" className={`${styles.tourVisual} ${styles.tourJourney}`} role="img">
      <div><span>01</span><strong>Locate public need</strong><small>Heat + people + vulnerability</small></div>
      <i aria-hidden="true" />
      <div><span>02</span><strong>Fund the best mix</strong><small>One budget, feasible projects</small></div>
      <i aria-hidden="true" />
      <div><span>03</span><strong>Defend the decision</strong><small>Place + price + sources</small></div>
    </div>;
  }
  if (step === 1) {
    return <div aria-label="Miniature map showing heat tiles, public sites, and four evidence layers" className={`${styles.tourVisual} ${styles.tourMap}`} role="img">
      <div className={styles.tourMapShape}><span className={styles.tourHotspot} /><span className={styles.tourHotspot} /><span className={styles.tourHotspot} /><b /><b /><b /><b /></div>
      <div className={styles.tourLayerStrip}><strong>LAYERS</strong><span className={styles.active}>Heat</span><span>Persistence</span><span>Exposure</span><span>Vulnerability</span></div>
      <p><span /> Selected investment site</p>
    </div>;
  }
  if (step === 2) {
    return <div aria-label="Miniature budget optimizer showing a one million dollar portfolio of twenty sites" className={`${styles.tourVisual} ${styles.tourPortfolio}`} role="img">
      <div className={styles.tourBudget}><small>INVESTMENT SCENARIO</small><strong>$1,000,000</strong><div><span /><span /><span className={styles.active} /></div></div>
      <div className={styles.tourPortfolioRows}><span><b>01</b><i>SHADE STRUCTURE</i><strong>Van Nuys / Herrick</strong></span><span><b>02</b><i>TREE CANOPY</i><strong>Pacoima Education Center</strong></span><span><b>03</b><i>SHADE STRUCTURE</i><strong>Glenoaks / Pierce</strong></span></div>
      <p><strong>20 sites</strong><span>zero vendor calls</span></p>
    </div>;
  }
  return <div aria-label="Miniature selected-site review showing street context, price, confidence, and sources" className={`${styles.tourVisual} ${styles.tourAudit}`} role="img">
    <div className={styles.tourStreet}><small>VERIFIED STREET CONTEXT</small><span><i /><i /><i /><i /></span><strong>Street image + segmentation</strong></div>
    <div className={styles.tourEvidence}><small>RECOMMENDED INTERVENTION</small><strong>Shade structure</strong><span>$50,000 LA allowance</span><hr /><b>Evidence confidence · 0.5</b><div><i /></div><p>AI explains these verified facts. Sources remain attached.</p></div>
  </div>;
}

function ProductTour({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(0);
  const current = tourSteps[step];
  return <div className={styles.tourBackdrop}><section aria-describedby="tour-body" aria-labelledby="tour-title" aria-modal="true" className={styles.tourPanel} role="dialog"><div className={styles.tourProgress}><span>{current.label}</span><span>{step + 1} / {tourSteps.length}</span></div><div className={styles.tourContent}><div><h2 id="tour-title">{current.title}</h2><p id="tour-body">{current.body}</p>{step === 0 ? <div className={styles.audienceLine}><span>For residents</span><span>For investors</span><span>For government</span></div> : null}</div><TourVisual step={step} /></div><div className={styles.tourActions}><button onClick={onClose} type="button">Skip tour</button><div>{step > 0 ? <button onClick={() => setStep((value) => value - 1)} type="button">Back</button> : null}<button onClick={() => { if (step === tourSteps.length - 1) onClose(); else setStep((value) => value + 1); }} type="button">{step === tourSteps.length - 1 ? "Explore the plan" : "Next"}</button></div></div></section></div>;
}

type RecommendationRailProps = { candidates: Candidate[]; portfolio: Portfolio; activeCandidateId: string; onSelect: (candidate: Candidate) => void };

function RecommendationRail({ candidates, portfolio, activeCandidateId, onSelect }: RecommendationRailProps) {
  return <aside className={styles.recommendationRail} aria-labelledby="recommendations-title">
    <div className={styles.railHeading}><div><p className={styles.eyebrow}>Optimized portfolio</p><h2 id="recommendations-title">Ranked recommendations</h2></div><span className={styles.countBadge}>{portfolio.selected_count} sites</span></div>
    <div className={styles.portfolioSummary} aria-label="Portfolio summary"><div><span>Budget allocated</span><strong>{compactCurrency(portfolio.total_cost_usd)}</strong></div><div><span>Modeled impact</span><strong>{portfolio.total_modeled_impact_score.toFixed(3)}</strong></div><div><span>Replan credits</span><strong>0</strong></div></div>
    <ol className={styles.recommendationList}>{candidates.map((candidate, index) => <li className={styles.recommendation} key={candidate.id}>
      <button aria-current={candidate.id === activeCandidateId ? "true" : undefined} className={styles.recommendationButton} onClick={() => onSelect(candidate)} type="button">
        <span className={styles.rank}>{String(index + 1).padStart(2, "0")}</span><span className={styles.recommendationBody}><span className={styles.interventionLabel}>{interventionLabel(candidate.intervention_type)}</span><strong>{candidate.site_name}</strong><span className={styles.recommendationMeta}><span>{compactCurrency(candidate.planning_cost_usd)} LA allowance</span><span>{impact(candidate).toFixed(3)} impact</span></span></span>
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

function StreetContextWindow({ context, loading, siteName, onClose }: { context: StreetViewContext | null; loading: boolean; siteName: string; onClose: () => void }) {
  const [segmented, setSegmented] = useState(true);
  const imageUrl = segmented ? context?.segmented_image_url : context?.original_image_url;
  return <section aria-busy={loading} aria-label={`Street context for ${siteName}`} className={styles.streetWindow}><header><div><p className={styles.eyebrow}>Verified street context</p><h2>{siteName}</h2></div><button aria-label="Close street context" onClick={onClose} type="button">Close</button></header>{loading ? <div className={styles.streetLoading}>Loading cached site evidence…</div> : context?.available && imageUrl ? <><div className={styles.streetImage}><Image alt={segmented ? `FortyGuard segmented street view for ${siteName}` : `Street view for ${siteName}`} fill sizes="(max-width: 832px) 100vw, 50vw" src={imageUrl} unoptimized /></div><div className={styles.streetControls}><button aria-pressed={!segmented} onClick={() => setSegmented(false)} type="button">Street image</button><button aria-pressed={segmented} onClick={() => setSegmented(true)} type="button">Segmentation</button><span>Image {context.image_date ? formatDate(context.image_date) : "date unavailable"}</span></div><ul className={styles.segmentList}>{Object.entries(context.segments).filter(([, value]) => value >= 0.5).sort((a, b) => b[1] - a[1]).map(([name, value]) => <li key={name}><span>{name}</span><strong>{value.toFixed(1)}%</strong></li>)}</ul><p className={styles.streetLimit}>{context.limitation} <a href={context.source_url} rel="noreferrer" target="_blank">{context.source_label}</a></p></> : <div className={styles.streetUnavailable}><strong>No verified segmentation for this site</strong><p>{context?.limitation ?? "Cached street context is unavailable."}</p></div>}</section>;
}

type MapWorkspaceProps = { budget: number; data: WorkspaceData; layer: LayerResponse; activeLayer: LayerName; layerLoading: boolean; optimizing: boolean; activeCandidateId: string; streetContext: StreetViewContext | null; streetLoading: boolean; streetVisible: boolean; onCloseStreet: () => void; onBudgetCommit: (budget: number) => void; onBudgetPreview: (budget: number) => void; onLayerChange: (layer: LayerName) => void; onSelectSite: (siteId: string) => void };

function MapWorkspace({ budget, data, layer, activeLayer, layerLoading, optimizing, activeCandidateId, streetContext, streetLoading, streetVisible, onCloseStreet, onBudgetCommit, onBudgetPreview, onLayerChange, onSelectSite }: MapWorkspaceProps) {
  const [legendHigh, legendLow] = legendEndpoints[activeLayer];
  return <section className={styles.mapWorkspace} aria-labelledby="map-title">
    <BudgetBar budget={budget} methodology={data.methodology} onCommit={onBudgetCommit} onPreview={onBudgetPreview} optimizing={optimizing} portfolio={data.portfolio} />
    <div className={styles.mapCanvas}><h1 className="sr-only" id="map-title">Pacoima cooling investment map</h1><MapView activeCandidateId={activeCandidateId} candidates={data.candidates.candidates} layer={layer} onSelectSite={onSelectSite} pilot={data.pilot} selectedCandidateIds={data.portfolio.selected_candidate_ids} />{streetVisible ? <StreetContextWindow context={streetContext} loading={streetLoading} onClose={onCloseStreet} siteName={data.site.site_name} /> : null}
      <div className={styles.heatLegend} aria-label={`${layerLabels[activeLayer]} normalized score legend, ${legendHigh} at the top and ${legendLow} at the bottom`}><span>{legendHigh}</span><div className={`${styles.legendRamp} ${styles[`${activeLayer}Ramp`]}`} aria-hidden="true"><i /><i /><i /><i /></div><span>{legendLow}</span></div>
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
    <div className={styles.interventionCallout}><p>Pacoima / Los Angeles price reference</p><h3>{intervention.label}</h3><div><span>{currency.format(intervention.planning_cost.estimate_usd)} planning allowance</span><span>{compactCurrency(intervention.planning_cost.low_usd)}–{compactCurrency(intervention.planning_cost.high_usd)} range</span></div><p className={styles.priceBasis}>{intervention.planning_cost.unit}. {intervention.planning_cost.basis}</p>{sources.filter((source) => intervention.planning_cost.source_ids.includes(source.id)).map((source) => <a href={source.url} key={source.id} rel="noreferrer" target="_blank">Price basis: {source.publisher}</a>)}</div>
    <section className={styles.impactSection}><div><p className={styles.eyebrow}>Modeled impact score</p><strong>{impact(candidate).toFixed(3)}</strong></div><p>Relative planning score from cached evidence and screening assumptions. It is not a temperature forecast or guaranteed outcome.</p></section>
    <dl className={styles.evidenceList}><div><dt>Observed heat</dt><dd>{tile.heat.average_temperature_c.toFixed(2)} °C tile average</dd></div><div><dt>Heat persistence</dt><dd>{tile.heat.persistence_hours.toFixed(2)} hours</dd></div><div><dt>Published patronage activity</dt><dd>{tile.exposure.published_patronage_activity?.toFixed(2) ?? "Not available"}</dd></div><div><dt>Vulnerability context</dt><dd>{tile.scores.vulnerability.toFixed(3)} modeled score</dd></div></dl>
    <details className={styles.scoreBreakdown}><summary>How the priority score is calculated</summary><dl>{Object.entries(tile.scores).map(([name, value]) => <div key={name}><dt>{name.replaceAll("_", " ")}</dt><dd>{value.toFixed(3)}{methodology.scoring.priority_weights[name] !== undefined ? ` · ${(methodology.scoring.priority_weights[name] * 100).toFixed(0)}% weight` : ""}</dd></div>)}</dl><p>Observed and published inputs are normalized to 0–1, then combined with the published weights. The intervention impact also applies feasibility and confidence screening.</p></details>
    <section className={styles.confidenceSection}><div className={styles.confidenceHeading}><span>Evidence confidence</span><strong>Unverified screening · {candidate.confidence.toFixed(1)}</strong></div><div className={styles.confidenceTrack} aria-label={`Confidence score ${candidate.confidence} out of 1`}><span style={{ width: `${candidate.confidence * 100}%` }} /></div><p>{intervention.uncertainty.summary}</p></section>
    <section className={styles.explanationSection} aria-labelledby="explanation-title">
      <div className={styles.explanationHeading}><div><p className={styles.eyebrow}>AI evidence assistant</p><h3 id="explanation-title">Why this site?</h3></div><button disabled={explanationLoading || siteLoading} onClick={onExplain} type="button">{explanationLoading ? "Explaining…" : explanation && explanationMode === "openrouter" ? "Run AI again" : explanation ? "Refresh explanation" : "Ask AI"}</button></div>
      <p className={styles.aiBoundary}>The AI explains the selected result. It never ranks sites or adds evidence.</p>
      {explanationError ? <p className={styles.explanationError} role="alert">{explanationError}</p> : null}
      {explanation?.fallback_reason ? <p className={styles.explanationError} role="status">{explanation.fallback_reason}</p> : null}
      {explanation ? <div className={styles.explanationBody}><p>{explanation.summary}</p><h4>Sources used</h4><ul className={styles.explanationSources}>{coreEvidenceSources.map((source) => <li key={source.url}><a href={source.url} rel="noreferrer" target="_blank">{source.label}</a></li>)}{sources.map((source) => <li key={source.id}><a href={source.url} rel="noreferrer" target="_blank">{source.publisher}: {source.title}</a></li>)}</ul><details><summary>Evidence and limitations</summary><h4>Evidence used</h4><ul>{explanation.why_selected.map((reason, index) => <li key={reason}>{reason}<small>Source record: {explanation.evidence[index]?.source_artifact_ids.join(", ")}</small></li>)}</ul><h4>Limits</h4><ul>{explanation.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></details><p className={styles.templateLabel}>{explanation.mode === "openrouter" ? `${explanation.model ?? "OpenRouter model"} · grounded evidence only` : explanationMode === "openrouter" ? "Deterministic fallback · OpenRouter is configured" : "Deterministic fallback · configure OpenRouter to enable AI wording"}</p></div> : <p className={styles.explanationPrompt}>{explanationMode === "openrouter" ? "Ox Alpha will explain only the verified facts shown for this site." : "The grounded fallback is ready; configure OpenRouter to enable AI wording."}</p>}
    </section>
    <details className={styles.methodology} id="methodology"><summary>Methodology & limitations</summary><div className={styles.methodologyBody}><p>{methodology.optimization.objective_note}</p><p>{methodology.interventions.cost_basis.disclaimer}</p><ul>{candidate.evidence.map((evidence) => <li key={evidence.kind}><strong>{evidence.kind.replaceAll("_", " ")}</strong><span>{evidence.statement}</span></li>)}</ul><h3>Source links</h3><ul className={styles.sourceList}>{sources.map((source) => <li key={source.id}><a href={source.url} rel="noreferrer" target="_blank">{source.publisher}: {source.title}</a><span>Retrieved {formatDate(source.retrieved_at)}</span></li>)}</ul><h3>Pilot limitations</h3><ul>{methodology.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></div></details>
  </aside>;
}

function LoadingShell() {
  return <main className={styles.loadingShell} aria-busy="true"><header className={styles.loadingHeader}><BrandMark /><span className={styles.loadingLine} /></header><div className={styles.loadingWorkspace}><div /><div /><div /></div><p className={styles.loadingAnnouncement} role="status">Loading and validating cached Pacoima evidence.</p></main>;
}

async function fetchWorkspace(budgetUsd?: number) {
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
    optimize(budgetUsd ?? pilot.default_budget_usd),
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
  const [streetContext, setStreetContext] = useState<StreetViewContext | null>(null);
  const [streetLoading, setStreetLoading] = useState(false);
  const [streetVisible, setStreetVisible] = useState(false);
  const [tourVisible, setTourVisible] = useState(false);
  const requestSequence = useRef(0);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setTourVisible(window.localStorage.getItem("coolspot-tour-v1") !== "complete");
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const closeTour = useCallback(() => {
    window.localStorage.setItem("coolspot-tour-v1", "complete");
    setTourVisible(false);
  }, []);

  const applyWorkspace = useCallback((loaded: Awaited<ReturnType<typeof fetchWorkspace>>) => {
    setFatalError(null);
    setBudget(loaded.data.portfolio.budget_usd);
    setActiveCandidateId(loaded.activeCandidateId);
    setLayers({ heat: loaded.heat });
    setExplanations({});
    setExplanationError(null);
    setOperationError(null);
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
    const loaded = await fetchWorkspace(data?.portfolio.budget_usd ?? budget);
    applyWorkspace(loaded);
  }, [applyWorkspace, budget, data?.portfolio.budget_usd]);

  const recommendations = useMemo(() => {
    if (!data) return [];
    const selected = new Set(data.portfolio.selected_candidate_ids);
    return data.candidates.candidates.filter((candidate) => selected.has(candidate.id)).sort((a, b) => impact(b) - impact(a) || a.id.localeCompare(b.id));
  }, [data]);

  const selectCandidate = useCallback(async (candidate: Candidate) => {
    if (!data) return;
    setStreetVisible(true); setStreetLoading(true); setOperationError(null); setExplanationError(null);
    if (candidate.id !== activeCandidateId) setSiteLoading(true);
    try {
      const [site, context] = await Promise.all([
        candidate.id === activeCandidateId ? Promise.resolve(data.site) : getSite(candidate.site_id),
        getStreetView(candidate.site_id),
      ]);
      setStreetContext(context); setActiveCandidateId(candidate.id); setData((current) => current ? { ...current, site } : current);
    }
    catch (caught) { setOperationError(`${caught instanceof Error ? caught.message : "Unable to load site evidence."} The previous site remains selected.`); }
    finally { setSiteLoading(false); setStreetLoading(false); }
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

  const requestExplanation = useCallback(async (candidate: Candidate, regenerate: boolean) => {
    if (!data || explanationLoading) return;
    const explanationKey = `${candidate.id}:${data.portfolio.budget_usd}`;
    setExplanationLoading(true); setExplanationError(null);
    try {
      const explanation = await getExplanation(candidate.site_id, candidate.id, data.portfolio.budget_usd, regenerate);
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

  return <div className={styles.appShell}><a className={styles.skipLink} href="#map-title">Skip to map workspace</a>{tourVisible ? <ProductTour onClose={closeTour} /> : null}<TopBar onRefreshComplete={retry} onTour={() => setTourVisible(true)} pilot={data.pilot} status={data.status} />{operationError ? <div className={styles.operationError} role="alert"><span>{operationError}</span><button aria-label="Dismiss error" onClick={() => setOperationError(null)} type="button">Dismiss</button></div> : null}<main className={styles.workspace}>
    <RecommendationRail activeCandidateId={activeCandidate.id} candidates={recommendations} onSelect={(candidate) => void selectCandidate(candidate)} portfolio={data.portfolio} />
    <MapWorkspace activeCandidateId={activeCandidate.id} activeLayer={activeLayer} budget={budget} data={data} layer={layers[activeLayer]} layerLoading={layerLoading} onBudgetCommit={(value) => void changeBudget(value)} onBudgetPreview={setBudget} onCloseStreet={() => setStreetVisible(false)} onLayerChange={(name) => void changeLayer(name)} onSelectSite={selectSite} optimizing={optimizing} streetContext={streetContext} streetLoading={streetLoading} streetVisible={streetVisible} />
    <EvidencePanel candidate={activeCandidate} explanation={explanations[explanationKey]} explanationError={explanationError} explanationLoading={explanationLoading} explanationMode={data.status.explanation_mode} methodology={data.methodology} onExplain={() => void requestExplanation(activeCandidate, Boolean(explanations[explanationKey]))} site={data.site} siteLoading={siteLoading} />
  </main></div>;
}
