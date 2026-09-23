// Role-based UI gating. This only decides what to *show*; the backend
// enforces every one of these rules independently, so hiding a control here
// is a convenience, never the security boundary.
//
// Ranks mirror backend/app/api/dependencies/auth.py (operator < supervisor
// < admin); a higher role includes everything below it.

export const ROLES = ['operator', 'supervisor', 'admin'];

export const ROLE_LABELS = {
  operator: 'Operator',
  supervisor: 'Supervisor',
  admin: 'Admin',
};

export const ROLE_DESCRIPTIONS = {
  operator: 'Monitors and runs analyses; cannot approve agent actions.',
  supervisor: 'Operator access, plus approves or rejects agent actions and reads the audit trail.',
  admin: 'Supervisor access, plus manages users and quarantines agents.',
};

const RANK = { operator: 1, supervisor: 2, admin: 3 };

// The superuser flag always means admin, matching the backend.
export const roleOf = (user) => {
  if (user?.is_superuser) return 'admin';
  return RANK[user?.role] ? user.role : 'operator';
};

export const hasRole = (user, minimum) => RANK[roleOf(user)] >= RANK[minimum];

const REQUIRED_ROLE = {
  approveActions: 'supervisor',
  viewAuditTrail: 'supervisor',
  manageAgents: 'admin',
  manageUsers: 'admin',
};

export const can = (user, action) => hasRole(user, REQUIRED_ROLE[action]);
