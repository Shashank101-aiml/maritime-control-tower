import React, { useEffect, useState } from 'react';
import { Radio } from 'lucide-react';

/**
 * Shows how current the readings are and when they next change.
 *
 * The upstream source publishes on 15-minute boundaries, so a correct,
 * live feed still shows the same observation time for minutes at a
 * stretch — visually identical to one that has died. This ticks every
 * second so the reader can see the feed is alive and know when the next
 * observation is due.
 */
export default function FreshnessIndicator({ freshness }) {
  const [, tick] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  if (!freshness?.fetchedAt) return null;

  const ageSeconds = Math.max(0, (Date.now() - new Date(freshness.fetchedAt).getTime()) / 1000);
  const age = ageSeconds < 60
    ? `${Math.floor(ageSeconds)}s ago`
    : `${Math.floor(ageSeconds / 60)} min ago`;

  // refreshInSeconds was captured at fetch time, so count down from it.
  const remaining = freshness.refreshInSeconds != null
    ? Math.max(0, Math.round(freshness.refreshInSeconds - ageSeconds))
    : null;
  const next = remaining == null
    ? null
    : remaining === 0
      ? 'due now'
      : remaining < 60
        ? `in ${remaining}s`
        : `in ${Math.ceil(remaining / 60)} min`;

  const observed = freshness.observedAt
    ? new Date(`${freshness.observedAt}Z`).toLocaleTimeString('en-GB', {
        hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false,
      }) + ' UTC'
    : null;

  return (
    <span className="freshness" title="Open-Meteo publishes a new observation every 15 minutes">
      <span className="freshness-dot" />
      <span>Fetched {age}</span>
      {observed && <span className="freshness-sep">· obs {observed}</span>}
      {next && <span className="freshness-sep">· next {next}</span>}
    </span>
  );
}
