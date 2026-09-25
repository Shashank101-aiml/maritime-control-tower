/** A transit time given in days, shown as whole days and hours: "12 days 2 hours",
 *  "1 day", "8 hours". */
export const formatTransit = (days) => {
  if (days == null || Number.isNaN(Number(days))) return '—';
  const totalHours = Math.max(1, Math.round(Number(days) * 24));
  const d = Math.floor(totalHours / 24);
  const h = totalHours % 24;
  const parts = [];
  if (d) parts.push(`${d} ${d === 1 ? 'day' : 'days'}`);
  if (h) parts.push(`${h} ${h === 1 ? 'hour' : 'hours'}`);
  return parts.join(' ');
};
