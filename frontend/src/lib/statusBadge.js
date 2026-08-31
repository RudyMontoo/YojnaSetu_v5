// Single source of truth for status -> badge color, so the same underlying
// data always renders the same color no matter which screen shows it.
// Found during a Problem 6 audit: StatusPage and ProfilePage each had their
// own inline ternary for the SAME application statuses, and disagreed
// (in_progress/submitted rendered saffron on one screen, gold on the other).

// Application Tracker (applications collection): in_progress | submitted |
// approved | rejected | disbursed. Two buckets beyond terminal states: the
// brand saffron for "still active" and green/red for the two real outcomes.
export function applicationBadgeColor(status) {
  if (status === 'approved' || status === 'disbursed') return 'green'
  if (status === 'rejected') return 'red'
  return 'saffron' // in_progress | submitted | any future non-terminal status
}

// Grievance tracking: recorded | filed_on_portal | resolved. "recorded" is
// a freshly-logged grievance awaiting the citizen's own CPGRAMS filing —
// nothing has gone wrong, so it must not read as red (a real bug found in
// the same audit: the old ternary's fallback branch made "recorded" red).
export function grievanceBadgeColor(status) {
  if (status === 'resolved') return 'green'
  if (status === 'filed_on_portal') return 'saffron'
  return 'gold' // recorded (or any future non-terminal status) — pending, not an error
}
