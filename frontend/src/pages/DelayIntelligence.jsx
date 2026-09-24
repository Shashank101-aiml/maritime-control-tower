import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Clock, RefreshCw, AlertCircle, Ship, Route as RouteIcon, Anchor, Info, FlaskConical, ChevronDown,
  TrendingUp, PauseCircle,
} from 'lucide-react';
import { getDelayOverview, assessDelay } from '../services/delayService';
import LoadingSpinner from '../components/LoadingSpinner';
import LiveVoyages from './LiveVoyages';

const label = { display: 'block', fontSize: '0.78rem', color: 'var(--text-subtle)', marginBottom: '6px' };

const day = (v) => (v == null ? '—' : `${Number(v).toFixed(v % 1 === 0 ? 0 : 1)} d`);
const pct = (v) => `${Math.round(v * 100)}%`;
const monthLabel = (m) => new Date(`${m}-01T00:00:00Z`).toLocaleDateString('en-GB', { month: 'short', year: '2-digit', timeZone: 'UTC' });

function Tile({ title, value, note, tone }) {
  return (
    <div className="kpi-card">
      <div>
        <div className="kpi-label">{title}</div>
        <div className="kpi-val" style={{ color: tone }}>{value}</div>
        {note && <div style={{ fontSize: '0.74rem', color: 'var(--text-subtle)', marginTop: '4px' }}>{note}</div>}
      </div>
    </div>
  );
}

/** Where journeys on this lane actually landed: min, p10, p25, median, p75, p90, max. */
function RangeBar({ t }) {
  const lo = t.min;
  const span = Math.max(t.max - lo, 1);
  const x = (v) => `${((v - lo) / span) * 100}%`;
  const legend = [
    ['fastest', t.min, 'var(--text-subtle)'],
    ['middle half starts', t.p25, 'var(--accent-cyan)'],
    ['median', t.median, 'var(--accent-cyan)'],
    ['middle half ends', t.p75, 'var(--accent-cyan)'],
    ['9 in 10 within', t.p90, 'var(--accent-amber)'],
    ['slowest', t.max, 'var(--text-subtle)'],
  ];
  return (
    <div>
      <div style={{ position: 'relative', height: '30px', margin: '10px 0 14px' }}>
        <div style={{ position: 'absolute', top: '13px', left: 0, right: 0, height: '4px', background: 'var(--surface-sunken)', borderRadius: '2px' }} />
        <div style={{ position: 'absolute', top: '8px', height: '14px', left: x(t.p25), width: `calc(${x(t.p75)} - ${x(t.p25)})`, background: 'var(--accent-cyan)', opacity: 0.5, borderRadius: '3px' }} />
        <div style={{ position: 'absolute', top: '4px', height: '22px', left: x(t.median), width: '3px', background: 'var(--accent-cyan)', borderRadius: '2px' }} />
        <div style={{ position: 'absolute', top: '6px', height: '18px', left: x(t.p90), width: '3px', background: 'var(--accent-amber)', borderRadius: '2px' }} />
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 16px', fontSize: '0.76rem' }}>
        {legend.map(([name, value, color]) => (
          <span key={name} style={{ color: 'var(--text-subtle)' }}>
            <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '2px', background: color, marginRight: '5px' }} />
            {name} <strong style={{ color: 'var(--text-body)' }}>{value} d</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

const ordinal = (n) => {
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  return `${n}${({ 1: 'st', 2: 'nd', 3: 'rd' })[n % 10] || 'th'}`;
};

/** Median ocean days per loading month, with the number of journeys behind each bar. */
function MonthlyChart({ months }) {
  if (months.length < 2) {
    return <p style={{ color: 'var(--text-subtle)', fontSize: '0.85rem' }}>Not enough months with several journeys each to show a trend for this lane.</p>;
  }
  const max = Math.max(...months.map((m) => m.median_days));
  const barW = 100 / months.length;
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: '4px', height: '150px', paddingTop: '18px' }} role="img"
      aria-label={`Median transit days by loading month: ${months.map((m) => `${monthLabel(m.month)} ${m.median_days}`).join(', ')}`}>
      {months.map((m) => (
        <div key={m.month} style={{ flex: `0 0 calc(${barW}% - 4px)`, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '100%' }}
          title={`${monthLabel(m.month)}: median ${m.median_days} days across ${m.journeys} journeys`}>
          <div style={{ fontSize: '0.66rem', color: 'var(--text-muted)', marginBottom: '2px' }}>{m.median_days}</div>
          <div style={{ width: '100%', height: `${Math.max(4, (m.median_days / max) * 100)}%`, background: 'var(--accent-cyan)', opacity: 0.75, borderRadius: '3px 3px 0 0' }} />
          <div style={{ fontSize: '0.64rem', color: 'var(--text-subtle)', marginTop: '4px', whiteSpace: 'nowrap' }}>{monthLabel(m.month)}</div>
          <div style={{ fontSize: '0.6rem', color: 'var(--text-subtle)', opacity: 0.7 }}>n={m.journeys}</div>
        </div>
      ))}
    </div>
  );
}

function PortSnapshot({ title, port }) {
  return (
    <div style={{ flex: '1 1 220px' }}>
      <div style={{ fontSize: '0.72rem', color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{title}</div>
      {!port ? (
        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>Not a port in the digital twin.</div>
      ) : !port.has_congestion_data ? (
        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}><strong>{port.twin_name}</strong> — no congestion data for this port.</div>
      ) : (
        <div style={{ marginTop: '4px', fontSize: '0.85rem', color: 'var(--text-main)' }}>
          <strong>{port.twin_name}</strong>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
            Congestion {port.congestion_index} ({ordinal(port.congestion_percentile)} percentile of its own history)
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
            {port.avg_wait_days} wait days · {port.berth_delay_hrs} h berth delay{port.as_of ? ` · week of ${port.as_of}` : ''}
          </div>
        </div>
      )}
    </div>
  );
}

function BacktestPanel({ backtest }) {
  const [open, setOpen] = useState(false);
  if (!backtest) return null;
  const d = backtest.transit_days;
  const seven = backtest.delayed?.find((x) => x.threshold_days === 7);
  return (
    <div className="panel">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
        style={{ display: 'flex', width: '100%', alignItems: 'center', gap: '8px', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-strong)', padding: 0, textAlign: 'left' }}>
        <FlaskConical size={17} color="var(--accent-amber)" />
        <span style={{ fontWeight: 600, fontSize: '1rem' }}>Why there is no prediction score here</span>
        <ChevronDown size={16} style={{ marginLeft: 'auto', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
      </button>
      <p style={{ fontSize: '0.86rem', color: 'var(--text-body)', margin: '10px 0 0', lineHeight: 1.55 }}>{backtest.conclusion}</p>
      {open && (
        <div style={{ marginTop: '14px', fontSize: '0.84rem', color: 'var(--text-body)', lineHeight: 1.6 }}>
          <p style={{ margin: '0 0 8px' }}>
            Tested on {backtest.n_journeys.toLocaleString()} real journeys across {backtest.n_lanes} lanes, {backtest.folds}: each round
            trains only on earlier loadings and is scored on later ones.
          </p>
          <ul style={{ margin: 0, paddingLeft: '18px' }}>
            <li>
              <strong>Transit days:</strong> the lane's own median was off by {d.lane_median_mae_days} days on average; LightGBM
              (distance, season, weekly port congestion) by {d.lightgbm_mae_days}. It beat the median in {d.folds_where_model_beat_baseline} of 3 rounds.
            </li>
            {seven && (
              <li>
                <strong>Running a week or more late:</strong> ranking journeys by the lane's own delay rate scored AUC {seven.lane_history_auc}
                ; LightGBM {seven.lightgbm_auc}; logistic regression {seven.logistic_auc} (0.5 is a coin flip).
              </li>
            )}
          </ul>
          <p style={{ margin: '8px 0 0', color: 'var(--text-subtle)' }}>
            The previous delay model reported an AUC of 0.996 on an anonymized supply-chain sample; a figure that high for a real
            delay problem was a sign of leakage, and the data had no real ports in it, so it was retired.
          </p>
        </div>
      )}
    </div>
  );
}

function DataQualityPanel({ quality }) {
  const [open, setOpen] = useState(false);
  if (!quality) return null;
  return (
    <div className="panel">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
        style={{ display: 'flex', width: '100%', alignItems: 'center', gap: '8px', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-strong)', padding: 0, textAlign: 'left' }}>
        <Info size={17} color="var(--accent-cyan)" />
        <span style={{ fontWeight: 600, fontSize: '1rem' }}>About the data</span>
        <span style={{ fontSize: '0.78rem', color: 'var(--text-subtle)' }}>
          {quality.rows_kept.toLocaleString()} of {quality.rows_in.toLocaleString()} journeys usable
        </span>
        <ChevronDown size={16} style={{ marginLeft: 'auto', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
      </button>
      {open && (
        <div style={{ marginTop: '12px', fontSize: '0.84rem', color: 'var(--text-body)' }}>
          <p style={{ margin: '0 0 8px' }}>
            The container-tracking export has messy dates (typo'd years, missing ports). A journey is used only when both ports and
            both dates exist and the sailing is plausible; nothing is repaired or guessed. What was left out:
          </p>
          <ul style={{ margin: 0, paddingLeft: '18px' }}>
            {Object.entries(quality.dropped).filter(([, n]) => n > 0).map(([reason, n]) => (
              <li key={reason}>{n.toLocaleString()} — {reason}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function LaneHistory({ setActiveTab }) {
  const [overview, setOverview] = useState(null);
  const [overviewError, setOverviewError] = useState(null);
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [loadingDate, setLoadingDate] = useState('');
  const [result, setResult] = useState(null);
  const [assessing, setAssessing] = useState(false);
  const [error, setError] = useState(null);

  const loadOverview = useCallback(async () => {
    setOverviewError(null);
    try {
      const data = await getDelayOverview();
      setOverview(data);
      // Start on the lane with the most history.
      const best = Object.entries(data.destinations_by_origin)
        .flatMap(([o, dests]) => dests.map((d) => ({ o, ...d })))
        .sort((a, b) => b.journeys - a.journeys)[0];
      if (best) { setOrigin(best.o); setDestination(best.destination); }
    } catch (err) {
      setOverviewError(err.message);
    }
  }, []);

  useEffect(() => { loadOverview(); }, [loadOverview]);

  const destinations = useMemo(() => overview?.destinations_by_origin?.[origin] ?? [], [overview, origin]);

  const assess = useCallback(async (o, d, when) => {
    if (!o || !d) return;
    setAssessing(true);
    setError(null);
    try {
      setResult(await assessDelay({ origin: o, destination: d, loadingDate: when }));
    } catch (err) {
      setError(err.message);
      setResult(null);
    } finally {
      setAssessing(false);
    }
  }, []);

  // Assess whenever the lane changes (the date only applies on the button).
  useEffect(() => { if (origin && destination) assess(origin, destination, loadingDate); }, [origin, destination]); // eslint-disable-line react-hooks/exhaustive-deps

  const onOriginChange = (value) => {
    setOrigin(value);
    const first = overview.destinations_by_origin[value]?.[0];
    setDestination(first ? first.destination : '');
  };

  if (overviewError) {
    return (
      <div className="page-wrapper">
        <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', borderColor: 'var(--accent-rose)' }}>
          <AlertCircle size={36} color="var(--accent-rose)" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: 'var(--text-main)' }}>{overviewError}</p>
        </div>
      </div>
    );
  }
  if (!overview) return <LoadingSpinner message="Loading journey data…" />;

  const a = result?.status === 'COMPLETED' ? result.assessment : null;
  const lane = a?.context?.lane;

  return (
    <div className="page-wrapper">
      <div className="section-header" style={{ marginBottom: '20px' }}>
        <div>
          <h1 className="section-title" style={{ fontSize: '1.8rem', color: 'var(--text-strong)' }}>
            <Clock size={28} color="var(--accent-cyan)" />
            Shipment Delay Intelligence
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: '4px', maxWidth: '900px' }}>
            How long real container journeys on a lane actually take, and how often they run late. Built from{' '}
            <strong>{overview.journeys.toLocaleString()}</strong> real journeys loaded {overview.loaded_from} to {overview.loaded_to},
            across {overview.lanes_usable} lanes with at least {overview.min_lane_journeys} journeys each.
          </p>
        </div>
        <button className="btn-secondary" onClick={loadOverview}><RefreshCw size={15} /> Reload</button>
      </div>

      <div className="panel" style={{ marginBottom: '20px' }}>
        <div className="section-header">
          <h3 className="section-title"><Ship size={17} /> Choose a lane</h3>
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); assess(origin, destination, loadingDate); }}
          style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-end' }}
        >
          <div>
            <label htmlFor="d-origin" style={label}>Loading port</label>
            <select id="d-origin" className="form-input" value={origin} onChange={(e) => onOriginChange(e.target.value)} style={{ minWidth: '190px' }}>
              {overview.origins.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="d-dest" style={label}>Discharge port</label>
            <select id="d-dest" className="form-input" value={destination} onChange={(e) => setDestination(e.target.value)} style={{ minWidth: '260px' }}>
              {destinations.map((d) => (
                <option key={d.destination} value={d.destination}>{d.destination} — {d.journeys} journeys, typically {d.median_days} d</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="d-date" style={label}>Planned loading date (optional)</label>
            <input id="d-date" className="form-input" type="date" value={loadingDate} onChange={(e) => setLoadingDate(e.target.value)} />
          </div>
          <button className="btn-action" type="submit" disabled={assessing || !destination}>
            <RefreshCw size={16} className={assessing ? 'spin' : ''} /> {assessing ? 'Assessing…' : 'Assess lane'}
          </button>
        </form>
        <p className="form-note" style={{ marginTop: '10px' }}>
          Only lanes with enough recorded journeys are offered. These are real ports; nothing here is a code or placeholder.
        </p>
      </div>

      {error && (
        <div className="glass-panel" role="alert" style={{ padding: '16px', marginBottom: '20px', borderColor: 'var(--accent-rose)' }}>
          <AlertCircle size={18} color="var(--accent-rose)" style={{ verticalAlign: '-3px', marginRight: '8px' }} />
          <span style={{ color: 'var(--text-main)' }}>{error}</span>
        </div>
      )}

      {result && result.status !== 'COMPLETED' && (
        <div className="glass-panel" style={{ padding: '16px', marginBottom: '20px', borderColor: 'var(--accent-amber)' }}>
          <PauseCircle size={18} color="var(--accent-amber)" style={{ verticalAlign: '-3px', marginRight: '8px' }} />
          <span style={{ color: 'var(--text-main)' }}>
            {result.status === 'PENDING_APPROVAL'
              ? `Held for human approval: ${result.reason}`
              : result.error || `Assessment ${result.status.toLowerCase()}.`}
          </span>
          {result.status === 'PENDING_APPROVAL' && setActiveTab && (
            <button className="btn-secondary" style={{ marginLeft: '12px' }} onClick={() => setActiveTab('governance')}>Open approvals</button>
          )}
        </div>
      )}

      {a && (
        <>
          <div className="kpi-grid" style={{ marginBottom: '20px' }}>
            <Tile title="Typical transit" value={day(a.transit_days.median)} note={`middle half: ${a.transit_days.p25}–${a.transit_days.p75} d`} />
            <Tile title="Plan for" value={day(a.transit_days.p90)} note="9 in 10 journeys arrived within this" tone={a.transit_days.p90 > a.transit_days.median * 1.5 ? 'var(--accent-amber)' : undefined} />
            <Tile
              title="Ran a week+ late"
              value={pct(a.delayed['7'].share)}
              note={`${a.delayed['7'].journeys} of ${a.journeys} took 7+ days over this lane's median`}
              tone={a.delayed['7'].share >= 0.3 ? 'var(--accent-rose)' : a.delayed['7'].share >= 0.15 ? 'var(--accent-amber)' : undefined}
            />
            <Tile title="Journeys on record" value={a.journeys} note={`${a.loaded_from} to ${a.loaded_to}`} />
          </div>

          <div className="content-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '20px', marginBottom: '20px' }}>
            <div className="panel">
              <div className="section-header"><h3 className="section-title"><RouteIcon size={17} /> How long journeys took</h3></div>
              <RangeBar t={a.transit_days} />
              {a.same_season && (
                <p style={{ fontSize: '0.84rem', color: 'var(--text-body)', margin: 0 }}>
                  <TrendingUp size={13} style={{ verticalAlign: '-2px', marginRight: '4px' }} />
                  Journeys loaded in this calendar month took a median <strong>{a.same_season.median_days} d</strong> ({a.same_season.journeys} journeys).
                </p>
              )}
            </div>

            <div className="panel">
              <div className="section-header"><h3 className="section-title"><Anchor size={17} /> On the digital twin</h3></div>
              {lane ? (
                <div style={{ fontSize: '0.88rem', color: 'var(--text-main)', marginBottom: '12px' }}>
                  Lane <strong>{lane.lane_id}</strong> · {Math.round(lane.distance_nm).toLocaleString()} nm. Ideal sailing time is about{' '}
                  <strong>{lane.ideal_transit_days} d</strong>, so real journeys typically took{' '}
                  <strong>{lane.typical_extra_days} d</strong> longer, which is time in port calls, transshipment and waiting.
                  {lane.risk != null && <div style={{ marginTop: '6px', color: 'var(--text-muted)' }}>Lane risk right now: <strong>{lane.risk}/100</strong> — {lane.risk_reason}</div>}
                  <div style={{ marginTop: '4px', fontSize: '0.75rem', color: 'var(--text-subtle)' }}>Ideal time: {lane.ideal_basis}.</div>
                </div>
              ) : (
                <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)', marginTop: 0 }}>
                  The digital twin has no direct lane between these two ports, so there is no ideal-time comparison or live lane risk for it.
                </p>
              )}
              <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
                <PortSnapshot title="Loading port now" port={a.context.origin_port} />
                <PortSnapshot title="Discharge port now" port={a.context.destination_port} />
              </div>
              {(a.context.origin_port?.has_congestion_data || a.context.destination_port?.has_congestion_data) && setActiveTab && (
                <button className="btn-secondary" style={{ marginTop: '12px', fontSize: '0.8rem' }} onClick={() => setActiveTab('congestion')}>Open Congestion</button>
              )}
            </div>
          </div>

          <div className="panel" style={{ marginBottom: '20px' }}>
            <div className="section-header">
              <h3 className="section-title"><Clock size={17} /> How this lane has moved (median transit by loading month)</h3>
            </div>
            <MonthlyChart months={a.monthly} />
            <p className="form-note" style={{ marginTop: '8px' }}>
              Real journeys grouped by the month they loaded; months with fewer than 3 journeys are left out rather than plotted from a couple of containers.
            </p>
          </div>

          <div className="panel" style={{ marginBottom: '20px' }}>
            <div className="section-header"><h3 className="section-title"><Info size={17} /> Read this with care</h3></div>
            <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.86rem', color: 'var(--text-body)', lineHeight: 1.6 }}>
              {a.caveats.map((c) => <li key={c}>{c}</li>)}
              <li>{a.confidence_basis}</li>
            </ul>
          </div>
        </>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <BacktestPanel backtest={overview.backtest} />
        <DataQualityPanel quality={overview.data_quality} />
      </div>
    </div>
  );
}

/** Two views of "is my shipment late": the live ships in your fleet against
 *  their due dates, and how long real journeys on a lane have taken. */
export default function DelayIntelligence({ user, setActiveTab }) {
  const [view, setView] = useState('voyages');
  return (
    <>
      <div className="page-wrapper" style={{ paddingBottom: 0 }}>
        <div style={{ display: 'flex', gap: '6px' }} role="tablist" aria-label="Shipment delay views">
          <button role="tab" aria-selected={view === 'voyages'} className={view === 'voyages' ? 'btn-action' : 'btn-secondary'} onClick={() => setView('voyages')}>Live voyages</button>
          <button role="tab" aria-selected={view === 'lanes'} className={view === 'lanes' ? 'btn-action' : 'btn-secondary'} onClick={() => setView('lanes')}>Lane history</button>
        </div>
      </div>
      {view === 'voyages' ? <LiveVoyages user={user} setActiveTab={setActiveTab} /> : <LaneHistory setActiveTab={setActiveTab} />}
    </>
  );
}
