import styles from "./planning-shell.module.css";

const recommendations = [
  {
    rank: "01",
    name: "Van Nuys / Herrick",
    intervention: "Shade structure",
    cost: "$50k",
    score: "0.209",
  },
  {
    rank: "02",
    name: "Pacoima Early Education Center",
    intervention: "Tree canopy",
    cost: "$50k",
    score: "0.209",
  },
  {
    rank: "03",
    name: "Glenoaks / Pierce",
    intervention: "Shade structure",
    cost: "$50k",
    score: "0.198",
  },
] as const;

const layers = ["Heat", "Persistence", "Exposure", "Vulnerability"] as const;

function BrandMark() {
  return (
    <svg aria-hidden="true" className={styles.brandMark} viewBox="0 0 32 32">
      <path d="M4 16a12 12 0 0 1 19.4-9.45L16 16Z" />
      <path d="M28 16a12 12 0 0 1-19.4 9.45L16 16Z" />
      <circle cx="16" cy="16" r="3.5" />
    </svg>
  );
}

function TopBar() {
  return (
    <header className={styles.topBar}>
      <div className={styles.brandLockup}>
        <BrandMark />
        <div>
          <p className={styles.brandName}>COOLSPOT AI</p>
          <p className={styles.brandDescriptor}>Cooling investment planner</p>
        </div>
      </div>

      <div className={styles.pilotIdentity}>
        <span className={styles.eyebrow}>Pilot area</span>
        <span className={styles.pilotName}>Pacoima, Los Angeles</span>
        <span className={styles.areaTag}>7.763 mi²</span>
      </div>

      <div className={styles.dataStatus} aria-label="Cached data status">
        <div className={styles.statusLine}>
          <span aria-hidden="true" className={styles.statusDot} />
          <span>CACHED ANALYSIS</span>
          <time dateTime="2024-07-15">15 JUL 2024</time>
        </div>
        <p>1,991,560 FortyGuard credits remaining</p>
      </div>
    </header>
  );
}

function RecommendationRail() {
  return (
    <aside className={styles.recommendationRail} aria-labelledby="recommendations-title">
      <div className={styles.railHeading}>
        <div>
          <p className={styles.eyebrow}>Optimized portfolio</p>
          <h2 id="recommendations-title">Ranked recommendations</h2>
        </div>
        <span className={styles.countBadge}>10 sites</span>
      </div>

      <div className={styles.portfolioSummary} aria-label="Portfolio summary">
        <div>
          <span>Budget allocated</span>
          <strong>$500k</strong>
        </div>
        <div>
          <span>Modeled impact</span>
          <strong>1.982</strong>
        </div>
        <div>
          <span>Replan credits</span>
          <strong>0</strong>
        </div>
      </div>

      <ol className={styles.recommendationList}>
        {recommendations.map((item) => (
          <li className={styles.recommendation} key={`${item.rank}-${item.name}`}>
            <div className={styles.rank}>{item.rank}</div>
            <div className={styles.recommendationBody}>
              <p className={styles.interventionLabel}>{item.intervention}</p>
              <h3>{item.name}</h3>
              <div className={styles.recommendationMeta}>
                <span>{item.cost} planning cost</span>
                <span>{item.score} impact</span>
              </div>
            </div>
          </li>
        ))}
      </ol>

      <div className={styles.railFooter}>
        <p>7 more selected sites</p>
        <span>152 compatible candidates screened</span>
      </div>
    </aside>
  );
}

function BudgetBar() {
  return (
    <section className={styles.budgetBar} aria-labelledby="budget-title">
      <div>
        <p className={styles.eyebrow}>Investment scenario</p>
        <h2 id="budget-title">$500,000 budget</h2>
      </div>
      <div className={styles.budgetScale} aria-label="Budget presets">
        <span>$250k</span>
        <span className={styles.activeBudget}>$500k</span>
        <span>$1M</span>
        <span>Custom</span>
      </div>
      <p className={styles.budgetNote}>Re-optimizes from cache</p>
    </section>
  );
}

function MapWorkspace() {
  return (
    <section className={styles.mapWorkspace} aria-labelledby="map-title">
      <BudgetBar />
      <div className={styles.mapCanvas}>
        <div className={styles.mapLabel}>
          <p className={styles.eyebrow}>Analysis boundary</p>
          <h1 id="map-title">Pacoima</h1>
          <p>2,001 FortyGuard tiles · EPSG:4326</p>
        </div>

        <div className={styles.heatLegend} aria-label="Heat score legend">
          <span>HIGHER</span>
          <div className={styles.legendRamp} aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </div>
          <span>LOWER</span>
        </div>

        <div className={styles.mapAttribution}>Real layers load from the cached Pacoima API</div>
      </div>

      <nav className={styles.layerDock} aria-label="Map layer hierarchy">
        <span className={styles.eyebrow}>Layers</span>
        <ul>
          {layers.map((layer, index) => (
            <li className={index === 0 ? styles.activeLayer : undefined} key={layer}>
              <span className={styles.layerSwatch} aria-hidden="true" />
              {layer}
            </li>
          ))}
        </ul>
      </nav>
    </section>
  );
}

function EvidencePanel() {
  return (
    <aside className={styles.evidencePanel} aria-labelledby="evidence-title">
      <div className={styles.evidenceHeader}>
        <div>
          <p className={styles.eyebrow}>Site evidence · Tile 1355</p>
          <h2 id="evidence-title">Van Nuys / Herrick</h2>
        </div>
        <span className={styles.selectedBadge}>Selected</span>
      </div>

      <div className={styles.interventionCallout}>
        <p>Recommended intervention</p>
        <h3>Shade structure</h3>
        <div>
          <span>$50,000 planning cost</span>
          <span>$35k–$75k range</span>
        </div>
      </div>

      <section className={styles.impactSection}>
        <div>
          <p className={styles.eyebrow}>Modeled impact score</p>
          <strong>0.209</strong>
        </div>
        <p>
          Relative planning score from heat, exposure, vulnerability, feasibility, and evidence
          confidence. It is not a temperature forecast.
        </p>
      </section>

      <dl className={styles.evidenceList}>
        <div>
          <dt>Observed heat</dt>
          <dd>35.45 °C tile average</dd>
        </div>
        <div>
          <dt>Heat persistence</dt>
          <dd>7.04 hours above 30 °C</dd>
        </div>
        <div>
          <dt>Published patronage activity</dt>
          <dd>79.79 boardings + alightings</dd>
        </div>
        <div>
          <dt>Vulnerability context</dt>
          <dd>0.622 modeled score</dd>
        </div>
      </dl>

      <section className={styles.confidenceSection}>
        <div className={styles.confidenceHeading}>
          <span>Evidence confidence</span>
          <strong>Unverified screening</strong>
        </div>
        <div className={styles.confidenceTrack} aria-label="Confidence score 0.5 out of 1">
          <span />
        </div>
        <p>Existing shade, right-of-way, utilities, and constructability require field review.</p>
      </section>

      <footer className={styles.evidenceFooter} id="methodology">
        <span className={styles.methodologyLabel}>Methodology & limitations</span>
        <span>5 traceable evidence records</span>
      </footer>
    </aside>
  );
}

export function PlanningShell() {
  return (
    <div className={styles.appShell}>
      <a className={styles.skipLink} href="#map-title">
        Skip to map workspace
      </a>
      <TopBar />
      <main className={styles.workspace}>
        <RecommendationRail />
        <MapWorkspace />
        <EvidencePanel />
      </main>
    </div>
  );
}
