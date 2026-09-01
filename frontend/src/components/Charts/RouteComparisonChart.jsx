import React from 'react';
import { GitCompare } from 'lucide-react';

/**
 * Placeholder for scored route alternatives.
 *
 * This previously compared three hardcoded corridors on invented hazard
 * scores, fuel savings and detour distances ("Corridor Beta … -15 tons
 * fuel save"), presented as model output.
 *
 * The Route Agent returns a single recommended route, not a ranked set,
 * so there is genuinely nothing to compare yet. Producing real
 * alternatives means scoring candidate routes in the agent — a feature,
 * not a chart fix.
 */
export default function RouteComparisonChart() {
  return (
    <div className="panel">
      <div className="section-header">
        <h3 className="section-title">
          <GitCompare size={17} color="var(--info)" />
          Corridor comparison
        </h3>
      </div>

      <div className="chart-empty">
        <p>No alternative corridors to compare.</p>
        <p className="chart-empty-sub">
          The Route Agent returns one recommended route. Ranked alternatives
          require it to generate and score candidate corridors.
        </p>
      </div>
    </div>
  );
}
