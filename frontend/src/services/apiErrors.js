// FastAPI reports validation failures as a list of {loc, msg}; everything
// else as a string. Turn either into one readable sentence.
export const failureMessage = async (res, fallback) => {
  const body = await res.json().catch(() => null);
  const detail = body?.detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc || []).slice(1).join('.') || 'input'}: ${d.msg}`).join('; ');
  }
  return detail || fallback;
};

export const jsonRequest = (method, payload) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});
