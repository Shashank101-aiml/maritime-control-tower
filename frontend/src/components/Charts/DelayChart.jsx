import React from 'react';
import { Clock } from 'lucide-react';

/**
 * Placeholder for per-port transit/berth delay.
 *
 * This previously rendered six hardcoded port delays ("Port Singapore
 * 14.5 hrs", "Gulf of Aden 18.0 hrs") presented as live estimates. None
 * of it came from the backend.
 *
 * The data to do this properly does exist — port_congestion.csv carries
 * real avg_wait_days and berth_delay_hrs per port — but it is not served
 * by any endpoint yet, and the congestion model predicts a congestion
 * flag rather than a wait time. Rather than keep the invented numbers,
 * this states what is missing.
 */
export default function DelayChart() {
  return (
    <div className="panel">
      <div className="section-header">
        <h3 className="section-title">
          <Clock size={17} color="var(--warning)" />
          Estimated transit &amp; port delays
        </h3>
      </div>

      <div className="chart-empty">
        <p>No delay estimates available.</p>
        <p className="chart-empty-sub">
          Per-port wait times need an endpoint over the recorded port-congestion
          history; the congestion model currently predicts a congestion flag, not
          an expected delay in hours.
        </p>
      </div>
    </div>
  );
}
