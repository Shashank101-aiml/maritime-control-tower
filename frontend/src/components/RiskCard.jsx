import React, { useState } from 'react';
import {
  ShieldCheck, ShieldAlert, MapPin, Ship,
  Sparkles, Clock, DollarSign, TrendingDown, TrendingUp, Hourglass, XCircle,
  ThumbsUp, ThumbsDown, PenLine, CheckCircle2,
} from 'lucide-react';
import { getRiskLevel } from '../types/Risk';

/**
 * Real human feedback on a completed decision (Slice 11) -- distinct
 * from the governance gate above: that's about whether the *pipeline*
 * could proceed, this is what a reviewer actually thought of the
 * result once it did. Approve/Reject record as-is; Modify requires a
 * real reason, matching what the backend enforces.
 */
function FeedbackButtons({ feedbackStatus, feedbackError, onSubmit }) {
  const [modifying, setModifying] = useState(false);
  const [reason, setReason] = useState('');

  if (feedbackStatus === 'submitted') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', color: 'var(--accent-emerald)', marginTop: '10px' }}>
        <CheckCircle2 size={14} /> Feedback recorded.
      </div>
    );
  }

  const submitting = feedbackStatus === 'submitting';

  return (
    <div style={{ marginTop: '10px' }}>
      {feedbackStatus === 'error' && (
        <p style={{ fontSize: '0.76rem', color: 'var(--accent-rose)', marginBottom: '6px' }}>{feedbackError}</p>
      )}
      {!modifying ? (
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button className="btn-secondary" disabled={submitting} onClick={() => onSubmit('APPROVED')} style={{ fontSize: '0.78rem' }}>
            <ThumbsUp size={13} /> Approve
          </button>
          <button className="btn-secondary" disabled={submitting} onClick={() => onSubmit('REJECTED')} style={{ fontSize: '0.78rem' }}>
            <ThumbsDown size={13} /> Reject
          </button>
          <button className="btn-secondary" disabled={submitting} onClick={() => setModifying(true)} style={{ fontSize: '0.78rem' }}>
            <PenLine size={13} /> Modify
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <input
            className="form-input"
            style={{ fontSize: '0.8rem' }}
            placeholder="What did you change, and why?"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              className="btn-secondary"
              disabled={submitting || !reason.trim()}
              onClick={() => onSubmit('MODIFIED', reason.trim())}
              style={{ fontSize: '0.78rem' }}
            >
              Submit
            </button>
            <button className="btn-secondary" disabled={submitting} onClick={() => setModifying(false)} style={{ fontSize: '0.78rem' }}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

const TONES = {
  CRITICAL: { fg: 'var(--danger)', bg: 'var(--danger-soft)', border: 'var(--danger-border)' },
  ELEVATED: { fg: 'var(--warning)', bg: 'var(--warning-soft)', border: 'var(--warning-border)' },
  NORMAL: { fg: 'var(--success)', bg: 'var(--success-soft)', border: 'var(--success-border)' },
};

/**
 * Real Decision Agent output (Slice 07) or an honest in-progress /
 * gated / failed state -- replaces what used to be a permanent
 * fabricated "mitigation_plan" string the backend never actually sent.
 */
function DecisionPanel({
  decisionStatus, decision, decisionMessage, onRequestDecision,
  feedbackStatus, feedbackError, onSubmitFeedback,
}) {
  if (decisionStatus === 'idle') {
    return (
      <button className="btn-action" style={{ width: '100%', justifyContent: 'center' }} onClick={onRequestDecision}>
        <Sparkles size={15} /> Get AI recommendation
      </button>
    );
  }

  if (decisionStatus === 'loading') {
    return (
      <button className="btn-secondary" style={{ width: '100%', justifyContent: 'center' }} disabled>
        <Hourglass size={15} className="spin" /> Running Decision Agent…
      </button>
    );
  }

  if (decisionStatus === 'pending_approval' || decisionStatus === 'rejected' || decisionStatus === 'error') {
    const tone = decisionStatus === 'error' ? 'var(--accent-rose)' : 'var(--warning)';
    return (
      <div>
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '0.85rem', color: 'var(--text-body)',
          background: 'var(--surface-subtle)', border: `1px solid ${tone}`, borderRadius: 'var(--radius)',
          padding: '12px 14px', marginBottom: '10px',
        }}>
          {decisionStatus === 'pending_approval' ? <Hourglass size={16} color={tone} style={{ flexShrink: 0, marginTop: 1 }} />
            : <XCircle size={16} color={tone} style={{ flexShrink: 0, marginTop: 1 }} />}
          <span>{decisionMessage}</span>
        </div>
        <button className="btn-secondary" style={{ width: '100%', justifyContent: 'center' }} onClick={onRequestDecision}>
          <Sparkles size={15} /> Try again
        </button>
      </div>
    );
  }

  // success
  const d = decision;
  const safer = d.risk_reduction > 0;
  const riskier = d.risk_reduction < 0;
  return (
    <div>
      <div style={{
        background: 'var(--surface-subtle)', border: '1px solid var(--border)',
        padding: '14px', borderRadius: 'var(--radius)', marginBottom: '12px',
      }}>
        <div style={{
          fontSize: '0.72rem', color: 'var(--text-subtle)', fontWeight: 600, marginBottom: '6px',
          display: 'flex', alignItems: 'center', gap: '6px', textTransform: 'uppercase', letterSpacing: '0.05em',
        }}>
          <Sparkles size={13} /> Decision Agent recommendation
        </div>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-body)', lineHeight: 1.5, marginBottom: '12px' }}>
          {d.recommendation}
        </p>
        <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', fontSize: '0.78rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: safer ? 'var(--accent-emerald)' : riskier ? 'var(--accent-rose)' : 'var(--text-subtle)' }}>
            {riskier ? <TrendingUp size={13} /> : <TrendingDown size={13} />} Risk {d.risk_reduction > 0 ? '-' : d.risk_reduction < 0 ? '+' : '±'}{Math.abs(d.risk_reduction)}
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-subtle)' }}>
            <Clock size={13} /> {d.expected_delay_days > 0 ? '+' : ''}{d.expected_delay_days}d
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-subtle)' }}>
            <DollarSign size={13} /> {d.estimated_cost_change_usd > 0 ? '+' : ''}${Math.abs(d.estimated_cost_change_usd).toLocaleString()}
          </span>
          <span style={{ color: 'var(--text-subtle)' }}>Confidence {Math.round(d.confidence * 100)}%</span>
        </div>
        {d.requires_human_approval && (
          <p style={{ fontSize: '0.76rem', color: 'var(--warning)', marginTop: '10px' }}>
            Flagged for human approval -- confidence or risk is outside this agent's auto-clear threshold.
          </p>
        )}
        {onSubmitFeedback && (
          <FeedbackButtons feedbackStatus={feedbackStatus} feedbackError={feedbackError} onSubmit={onSubmitFeedback} />
        )}
      </div>
      <button className="btn-secondary" style={{ width: '100%', justifyContent: 'center' }} onClick={onRequestDecision}>
        <Sparkles size={15} /> Recalculate
      </button>
    </div>
  );
}

export default function RiskCard({
  risk, decisionStatus, decision, decisionMessage, onRequestDecision,
  feedbackStatus, feedbackError, onSubmitFeedback,
}) {
  if (!risk) return null;

  const level = getRiskLevel(risk.risk_score);
  const isCritical = level === 'CRITICAL';
  const tone = TONES[level] || TONES.NORMAL;

  return (
    <div className="panel" style={{ borderColor: isCritical ? tone.border : 'var(--border)' }}>
      <div className="section-header">
        <div className="section-title">
          {isCritical
            ? <ShieldAlert size={17} color={tone.fg} />
            : <ShieldCheck size={17} color={tone.fg} />}
          {risk.category}
        </div>
        <span
          className="status-badge"
          style={{ background: tone.bg, borderColor: tone.border, color: tone.fg }}
        >
          {level} · {risk.risk_score}/100
        </span>
      </div>

      {risk.location && (
        <div style={{ marginBottom: '14px' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            fontSize: '0.8rem', color: 'var(--text-subtle)'
          }}>
            <MapPin size={13} />
            {risk.location}
            <span style={{ color: 'var(--border-strong)' }}>·</span>
            <Ship size={13} />
            {!risk.vessels_configured
              ? 'vessel tracking not configured'
              : risk.vessel_count === null
                ? 'vessel count unavailable'
                : `${risk.vessel_count} vessel${risk.vessel_count === 1 ? '' : 's'} in this corridor`}
          </div>

          {risk.vessels?.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
              {risk.vessels.slice(0, 6).map((v) => (
                <span key={v.mmsi} className="status-badge" style={{
                  fontSize: '0.7rem', background: 'var(--surface-subtle)',
                  borderColor: 'var(--border)', color: 'var(--text-body)'
                }}>
                  {v.name || `MMSI ${v.mmsi}`}
                </span>
              ))}
              {risk.vessel_count > 6 && (
                <span style={{ fontSize: '0.72rem', color: 'var(--text-subtle)', alignSelf: 'center' }}>
                  +{risk.vessel_count - 6} more
                </span>
              )}
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
        <div className="result-metric">
          <div className="result-metric-label">Impact severity</div>
          <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-strong)' }}>{risk.impact}</div>
        </div>
        <div className="result-metric">
          <div className="result-metric-label">Probability</div>
          <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-strong)' }}>{risk.likelihood}</div>
        </div>
      </div>

      {onRequestDecision && (
        <DecisionPanel
          decisionStatus={decisionStatus}
          decision={decision}
          decisionMessage={decisionMessage}
          onRequestDecision={onRequestDecision}
          feedbackStatus={feedbackStatus}
          feedbackError={feedbackError}
          onSubmitFeedback={onSubmitFeedback}
        />
      )}
    </div>
  );
}
