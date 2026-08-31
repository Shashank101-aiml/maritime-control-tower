/**
 * @typedef {Object} TelemetryEvent
 * @property {string} id - Unique identifier for the event
 * @property {string} event_type - Type of event (e.g., Storm, Piracy Warning, Port Congestion)
 * @property {string} location - Geographic or maritime region (e.g., Arabian Sea, Gulf of Aden)
 * @property {string} severity - Severity level: "HIGH" | "MEDIUM" | "LOW"
 * @property {string} timestamp - UTC or relative timestamp string
 * @property {Object} [coordinates] - Optional latitude and longitude
 * @property {string} [vessel_id] - Associated vessel identifier if applicable
 */

/**
 * Validates and normalizes a telemetry event object received from the API.
 * @param {Object} rawEvent
 * @returns {TelemetryEvent}
 */
export const createEvent = (rawEvent = {}) => {
  return {
    id: rawEvent.id || `EVT-${Math.floor(1000 + Math.random() * 9000)}`,
    event_type: rawEvent.event_type || 'Unknown Telemetry Event',
    location: rawEvent.location || 'International Waters',
    severity: (rawEvent.severity || 'LOW').toUpperCase(),
    timestamp: rawEvent.timestamp || new Date().toUTCString(),
    coordinates: rawEvent.coordinates || { lat: 0.0, lng: 0.0 },
    vessel_id: rawEvent.vessel_id || 'FLEET-GENERAL',
  };
};

/**
 * Helper to get color code for severity
 * @param {string} severity
 * @returns {string} CSS variable or hex color
 */
export const getSeverityColor = (severity) => {
  switch ((severity || '').toUpperCase()) {
    case 'HIGH':
    case 'CRITICAL':
      return 'var(--accent-rose)';
    case 'MEDIUM':
    case 'MODERATE':
      return 'var(--accent-amber)';
    case 'LOW':
    default:
      return 'var(--accent-cyan)';
  }
};
