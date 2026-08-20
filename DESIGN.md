---
name: Urban Resilience Framework
colors:
  surface: '#031427'
  surface-dim: '#031427'
  surface-bright: '#2a3a4f'
  surface-container-lowest: '#000f21'
  surface-container-low: '#0b1c30'
  surface-container: '#102034'
  surface-container-high: '#1b2b3f'
  surface-container-highest: '#26364a'
  on-surface: '#d3e4fe'
  on-surface-variant: '#c6c6cd'
  inverse-surface: '#d3e4fe'
  inverse-on-surface: '#213145'
  outline: '#909097'
  outline-variant: '#45464d'
  surface-tint: '#bec6e0'
  primary: '#bec6e0'
  on-primary: '#283044'
  primary-container: '#0f172a'
  on-primary-container: '#798098'
  inverse-primary: '#565e74'
  secondary: '#4fdbc8'
  on-secondary: '#003731'
  secondary-container: '#04b4a2'
  on-secondary-container: '#003f38'
  tertiary: '#ffb2b7'
  on-tertiary: '#67001b'
  tertiary-container: '#39000b'
  on-tertiary-container: '#ee3a5a'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#71f8e4'
  secondary-fixed-dim: '#4fdbc8'
  on-secondary-fixed: '#00201c'
  on-secondary-fixed-variant: '#005048'
  tertiary-fixed: '#ffdadb'
  tertiary-fixed-dim: '#ffb2b7'
  on-tertiary-fixed: '#40000d'
  on-tertiary-fixed-variant: '#92002a'
  background: '#031427'
  on-background: '#d3e4fe'
  surface-variant: '#26364a'
  heat-max: '#991B1B'
  heat-high: '#EF4444'
  heat-mid: '#F97316'
  heat-low: '#FBBF24'
  cool-optimal: '#10B981'
  cool-base: '#064E3B'
  ui-panel: '#1E293B'
  ui-border: '#334155'
typography:
  display-lg:
    fontFamily: Public Sans
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Public Sans
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-md:
    fontFamily: Public Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  data-num:
    fontFamily: JetBrains Mono
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 24px
  headline-lg-mobile:
    fontFamily: Public Sans
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 16px
  margin-page: 24px
  panel-width: 400px
  control-bar-height: 64px
---

## Brand & Style

The design system for this product is rooted in the "Civic Tech Modern" aesthetic—a philosophy that balances the sobriety of government administration with the precision of advanced geospatial intelligence. It is designed to evoke a sense of **authoritative urgency**; the UI does not just present data, it builds a "defensible" case for municipal investment.

The style is a hybrid of **Minimalism** and **Modern Corporate**, utilizing heavy whitespace to handle high information density without overwhelming the user. We avoid decorative flourishes in favor of structural clarity, using a "form follows function" approach that mirrors the technical, auditable nature of urban planning. The emotional response is one of **calculated optimism**: providing clear, actionable pathways to mitigate the climate crisis through rigorous data.

## Colors

The palette utilizes a "Heat & Cool" scale to create an immediate mental model for the user. 
- **The Foundation:** A deep Navy (`#0F172A`) and Slate backdrop provides the "Trust & Authority" required for municipal tools, ensuring that vibrant data layers remain the focal point.
- **The Semantic Heat Scale:** Vivid oranges and reds are reserved strictly for FortyGuard heat data and hotspot identification. This scale transitions from a cautionary Amber to an urgent Deep Red.
- **The Intervention Teal:** A crisp Emerald/Teal is used for "Cooling Interventions" and the budget optimizer. This color represents the solution—the physical implementation of trees, shade, and cool pavement.
- **Functional Use:** Light text on dark backgrounds ensures high contrast for night-shift planners or emergency management contexts, while maintaining a sophisticated, technical feel.

## Typography

The typography strategy prioritizes **legibility and data density**. 
- **Public Sans** (Headlines): Chosen for its institutional clarity and clean, geometric forms that feel both modern and official.
- **Inter** (Body): Used for all descriptive text and evidence reasoning, providing excellent readability at various sizes.
- **JetBrains Mono** (Labels/Data): A technical monospaced font is used for all "Auditable Evidence"—coordinates, budget figures, impact scores, and data timestamps. This distinguishes raw data from narrative descriptions, reinforcing the "Technical/Auditable" tone.

## Layout & Spacing

The layout follows a **Fixed-Fluid Hybrid** model optimized for professional desktop displays:
- **Primary Viewport:** A fluid 3D/Map interface that fills the available screen space.
- **Analytical Sidebars:** Fixed-width (400px) drawers for site evidence and ranked recommendations, allowing for deep vertical scrolling of data cards without losing map context.
- **Control Overlay:** A top-aligned "Budget Bar" and bottom-aligned "Layer Control" that use 24px safe-area margins from the screen edge.
- **Spacing Rhythm:** Based on a 4px grid. Use 16px (4 units) for standard component spacing and 24px (6 units) for sectional separation.

## Elevation & Depth

Hierarchy is established through **Tonal Layers** and **Low-Contrast Outlines** rather than traditional shadows.
- **Level 0 (Base):** The interactive map.
- **Level 1 (Panels):** UI containers use a slightly lighter slate (`#1E293B`) than the background, with a 1px border (`#334155`).
- **Level 2 (Active Controls/Modals):** These use a subtle backdrop blur (12px) to suggest they are floating above the map, but maintain a sharp, "glass-brutalist" border to feel structured rather than whimsical. 
- **Depth Cues:** Depth is also conveyed through saturation; "inactive" data layers are desaturated, while "active" candidate sites and the selected portfolio glow with higher vibrancy.

## Shapes

The design uses **Soft (0.25rem)** roundedness. This minimal rounding provides just enough modern polish to prevent the UI from feeling "dated" or "legacy," while maintaining the professional, "square-jawed" look of technical software. High-density data cards and map markers use this 4px radius consistently. Budget sliders and major action buttons may use a full pill-shape to distinguish them from data containers.

## Components

- **High-Contrast Data Cards:** Used for intervention candidates. They must include a header with a `label-caps` category (e.g., SHADE STRUCTURE), a large `data-num` impact score, and a clear "Traceable Evidence" section.
- **Professional Mapping Controls:** Layer toggles should use a "button group" style with clear active states using the Secondary Teal color.
- **Budget Management Interface:** A custom slider with tick marks at `$250k`, `$500k`, and `$1M`. The track should fill with the Secondary Teal as it is adjusted, symbolizing "investment coverage."
- **KPI Summary Chips:** Small, dark-bordered containers with a monospaced value and a small icon (e.g., a thermometer for heat reduction, a leaf for canopy increase).
- **Site Evidence Drawer:** A heavy-duty vertical component featuring "Source Links" and "Confidence Meters" (horizontal bars showing model certainty).
- **Status Indicators:** A "Data Freshness" indicator in the corner of the map, using `label-caps` to show "LIVE" (Green) or "CACHED" (Amber).