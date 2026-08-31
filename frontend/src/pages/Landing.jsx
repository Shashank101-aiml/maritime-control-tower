import React from 'react';
import {
  Anchor, ArrowRight, Radar, ShieldCheck, Cpu, Fuel, Clock, ScrollText
} from 'lucide-react';

const CAPABILITIES = [
  {
    icon: Radar,
    title: 'Congestion prediction',
    body: 'Forecasts port and vessel congestion from real AIS tracks, loitering events, and weekly port indices across three independent data sources.',
  },
  {
    icon: Clock,
    title: 'Shipment delay risk',
    body: 'Scores every order against carrier, route, and plant-capacity context so planners see which shipments are trending late before they are.',
  },
  {
    icon: Fuel,
    title: 'Fuel & cost savings',
    body: 'Predicts trip fuel burn and benchmarks it against the best efficiency actually observed on that ship type and route.',
  },
  {
    icon: Cpu,
    title: 'Multi-agent workflow',
    body: 'Ingestion, risk, routing, and explanation agents hand structured outputs to one another instead of running as one monolithic script.',
  },
  {
    icon: ShieldCheck,
    title: 'Runtime governance',
    body: 'Every agent action passes identity, authorisation, and confidence checks. Low-confidence decisions pause for human approval.',
  },
  {
    icon: ScrollText,
    title: 'Full audit trail',
    body: 'Each execution is traced end to end — inputs, outputs, confidence, policy decisions — so any recommendation can be reconstructed.',
  },
];

const STATS = [
  { value: '138K', label: 'Vessel-weeks & port-weeks modelled' },
  { value: '3', label: 'Predictive models in production' },
  { value: '10', label: 'Maritime & logistics data sources' },
  { value: '0.82', label: 'Congestion model ROC-AUC' },
];

export default function Landing({ onEnter }) {
  return (
    <div className="landing">
      <nav className="landing-nav">
        <div className="brand">
          <Anchor className="brand-icon" size={22} strokeWidth={2.2} />
          <div>
            <div className="brand-title">Maritime Control</div>
            <div className="brand-sub">Agentic fleet &amp; logistics intelligence</div>
          </div>
        </div>

        <div className="landing-nav-links">
          <button className="landing-nav-link" onClick={() => scrollToId('capabilities')}>Capabilities</button>
          <button className="landing-nav-link" onClick={() => scrollToId('platform')}>Platform</button>
          <button className="landing-nav-link" onClick={() => scrollToId('governance')}>Governance</button>
        </div>

        <button className="btn-action" onClick={onEnter}>
          Open console <ArrowRight size={15} />
        </button>
      </nav>

      <section className="landing-hero">
        <div>
          <div className="landing-eyebrow">Agentic AI Control Tower</div>
          <h1>Predict disruption before it reaches your fleet.</h1>
          <p className="landing-lede">
            Maritime Control ingests live vessel, port, and logistics data, forecasts congestion
            and delay risk with trained models, and lets governed AI agents recommend the routing
            response — with a human in the loop wherever confidence is low.
          </p>
          <div className="landing-cta-row">
            <button className="btn-action" onClick={onEnter}>
              Open console <ArrowRight size={15} />
            </button>
            <button className="btn-secondary" onClick={() => scrollToId('capabilities')}>
              See capabilities
            </button>
          </div>
        </div>

        <HeroPreview />
      </section>

      <section className="landing-section" id="capabilities">
        <div className="landing-eyebrow">Capabilities</div>
        <h2>One console for prediction, routing, and oversight.</h2>
        <p className="landing-lede">
          Most visibility tools surface alerts and stop there. This one scores the risk, proposes
          the action, and shows its work.
        </p>

        <div className="landing-grid">
          {CAPABILITIES.map(({ icon: Icon, title, body }) => (
            <div className="landing-card" key={title}>
              <div className="landing-card-icon"><Icon size={19} /></div>
              <h3>{title}</h3>
              <p>{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-section" id="platform">
        <div className="landing-eyebrow">Platform</div>
        <h2>Built on real maritime data, not demo fixtures.</h2>
        <p className="landing-lede">
          Models are trained on AIS vessel tracks, loitering events, port congestion indices,
          shipment records, and fuel logs — cleaned, feature-engineered, and checked for leakage.
        </p>

        <div className="landing-stat-row">
          {STATS.map(({ value, label }) => (
            <div key={label}>
              <div className="landing-stat-val">{value}</div>
              <div className="landing-stat-label">{label}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-section" id="governance">
        <div className="landing-eyebrow">Governance</div>
        <h2>Autonomy with a stop button.</h2>
        <p className="landing-lede">
          Every agent is registered with a risk level, criticality, and confidence threshold.
          When an agent's confidence falls below its threshold — or its action is classed
          critical — the workflow pauses and waits for a human decision rather than proceeding.
          Agents can be quarantined instantly, and every execution is written to an audit log.
        </p>
        <div className="landing-cta-row" style={{ marginTop: '28px' }}>
          <button className="btn-action" onClick={onEnter}>
            Explore the console <ArrowRight size={15} />
          </button>
        </div>
      </section>

      <footer className="landing-footer">
        Maritime Control · Agentic AI control tower for supply chain disruption monitoring
      </footer>
    </div>
  );
}

function scrollToId(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/** Stylised console preview — deliberately abstract shapes rather than
 *  fabricated metrics, so nothing here reads as a real reading. */
function HeroPreview() {
  const bars = [42, 66, 38, 78, 54, 88, 61];
  return (
    <div className="hero-preview" aria-hidden="true">
      <div className="hero-preview-bar">
        <span className="hero-preview-dot" />
        <span className="hero-preview-dot" />
        <span className="hero-preview-dot" />
      </div>

      <div className="hero-preview-grid">
        <div className="hero-preview-tile">
          <div className="hero-preview-num">42</div>
          <div className="hero-preview-cap">Active vessels</div>
        </div>
        <div className="hero-preview-tile">
          <div className="hero-preview-num" style={{ color: 'var(--warning)' }}>3</div>
          <div className="hero-preview-cap">Open alerts</div>
        </div>
        <div className="hero-preview-tile">
          <div className="hero-preview-num" style={{ color: 'var(--green)' }}>8</div>
          <div className="hero-preview-cap">Agents online</div>
        </div>
      </div>

      <div className="hero-preview-bars">
        {bars.map((h, i) => (
          <div key={i} className="hero-preview-bar-col" style={{ height: `${h}%` }} />
        ))}
      </div>
    </div>
  );
}
