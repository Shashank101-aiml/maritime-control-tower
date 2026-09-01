/**
 * @typedef {Object} TelemetryEvent
 * @property {string} id
 * @property {string} event_type
 * @property {string|null} location
 * @property {string} severity - CRITICAL | HIGH | WARNING | LOW | INFO
 * @property {string|null} timestamp
 * @property {{lat:number, lng:number}|null} coordinates
 * @property {string|null} description
 * @property {Object|null} conditions - raw sea-state readings when present
 * @property {string|null} vessel_id
 */

/**
 * Normalises an event from the API.
 *
 * Deliberately does NOT invent values. The previous version defaulted
 * vessel_id to "FLEET-GENERAL", coordinates to 0,0 (Null Island),
 * location to "International Waters" and timestamp to now — so corridor
 * sea-state readings, which carry no vessel at all, were rendered as
 * though a vessel had reported them. Missing data is null and the UI
 * omits it.
 */
export const createEvent = (rawEvent = {}) => {
  const coords =
    rawEvent.coordinates ??
    (rawEvent.latitude != null && rawEvent.longitude != null
      ? { lat: rawEvent.latitude, lng: rawEvent.longitude }
      : null);

  return {
    // Stable identity: the old version used Math.random(), producing a
    // new key on every render.
    id: rawEvent.id ?? `${rawEvent.location ?? 'unknown'}-${rawEvent.timestamp ?? ''}`,
    event_type: rawEvent.event_type ?? 'Unclassified reading',
    location: rawEvent.location ?? null,
    severity: String(rawEvent.severity ?? 'INFO').toUpperCase(),
    timestamp: rawEvent.timestamp ?? null,
    coordinates: coords,
    description: rawEvent.description ?? null,
    conditions: rawEvent.conditions ?? null,
    vessel_id: rawEvent.vessel_id ?? null,
  };
};

/** The severity bands the backend actually emits. */
export const SEVERITY_LEVELS = ['CRITICAL', 'HIGH', 'WARNING', 'LOW', 'INFO'];

const SEVERITY_TONES = {
  CRITICAL: { fg: 'var(--danger)', bg: 'var(--danger-soft)', border: 'var(--danger-border)' },
  HIGH: { fg: 'var(--danger)', bg: 'var(--danger-soft)', border: 'var(--danger-border)' },
  WARNING: { fg: 'var(--warning)', bg: 'var(--warning-soft)', border: 'var(--warning-border)' },
  LOW: { fg: 'var(--info)', bg: 'var(--info-soft)', border: 'var(--info-border)' },
  INFO: { fg: 'var(--success)', bg: 'var(--success-soft)', border: 'var(--success-border)' },
};

/**
 * Full tone for a severity. The previous helper had no WARNING or INFO
 * case, so both fell through to the LOW colour — a warning-level reading
 * was indistinguishable from a calm one.
 */
export const getSeverityTone = (severity) =>
  SEVERITY_TONES[String(severity || '').toUpperCase()] || SEVERITY_TONES.INFO;

export const getSeverityColor = (severity) => getSeverityTone(severity).fg;

/** "INFO HAZARD" reads as nonsense; calm conditions are not a hazard. */
export const getSeverityLabel = (severity) => {
  const key = String(severity || '').toUpperCase();
  return key === 'INFO' ? 'NOMINAL' : `${key} HAZARD`;
};
