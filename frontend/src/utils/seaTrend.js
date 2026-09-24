// Turns a corridor's recorded readings into what a person needs at a
// glance: which way it moved since the previous reading, and how it has
// ranged over the window. Everything here is arithmetic on recorded
// points -- nothing is smoothed or filled in.

// The source publishes every 15 minutes; a longer silence means the app
// wasn't collecting, so the line is broken there rather than joined.
export const GAP_MS = 40 * 60 * 1000;

export const parseTime = (value) => Date.parse(value.endsWith('Z') ? value : `${value}Z`);

const METRICS = {
  wave_height_m: { unit: 'm', label: 'Wave height', decimals: 2, flatBelow: 0.005 },
  wind_gusts_kmh: { unit: 'km/h', label: 'Gusts', decimals: 1, flatBelow: 0.05 },
};

const round = (value, decimals) => Number(value.toFixed(decimals));

/** Wave height where the corridor has any, otherwise gusts (Suez has no
 *  wave data in the source). */
export const pickMetric = (points) =>
  (points.some((p) => p.wave_height_m != null) ? 'wave_height_m' : 'wind_gusts_kmh');

export const summarizeTrend = (points) => {
  if (!points || points.length === 0) return null;
  const key = pickMetric(points);
  const meta = METRICS[key];
  const valid = points
    .filter((p) => p[key] != null)
    .map((p) => ({ t: parseTime(p.time), v: p[key] }));
  if (valid.length === 0) return null;

  const first = valid[0];
  const last = valid[valid.length - 1];
  const prev = valid.length > 1 ? valid[valid.length - 2] : null;
  const values = valid.map((p) => p.v);

  const delta = prev ? round(last.v - prev.v, meta.decimals) : null;
  let direction = null;
  if (delta != null) direction = Math.abs(delta) < meta.flatBelow ? 'flat' : delta > 0 ? 'up' : 'down';

  return {
    key, ...meta, valid, first, last, prev, delta, direction,
    windowDelta: valid.length > 1 ? round(last.v - first.v, meta.decimals) : null,
    spanMs: last.t - first.t,
    min: Math.min(...values),
    max: Math.max(...values),
  };
};

export const formatSpan = (ms) => {
  const minutes = Math.round(ms / 60000);
  if (minutes < 90) return `${minutes} min`;
  const hours = ms / 3600000;
  return hours < 48 ? `${Math.round(hours)} h` : `${Math.round(hours / 24)} days`;
};

export const formatClock = (t) =>
  new Date(t).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false }) + ' UTC';
