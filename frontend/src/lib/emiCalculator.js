// Standard reducing-balance EMI math — the same formula every bank uses —
// plus the moratorium handling these NSFDC schemes actually carry. No
// external data dependency; the scheme-specific rate/moratorium/cap inputs
// come from nsfdcSchemes.js.
//
// The moratorium is not cosmetic. Every NSFDC scheme in this module has one
// (3–12 months), and during it the loan is still accruing interest. Two
// treatments exist and they produce materially different numbers, so the
// caller must pick one and the UI must say which is shown:
//
//   MORATORIUM_CAPITALISE  — the citizen pays nothing during the moratorium;
//     accrued interest is added to the principal, and EMIs are computed on
//     that larger balance. Cheaper now, more expensive overall.
//   MORATORIUM_SERVICE_INTEREST — the citizen pays interest-only each
//     moratorium month; principal is untouched, so EMIs are computed on the
//     original amount. Costs money immediately, less overall.
//
// Passing no moratorium options reproduces the plain no-moratorium schedule.

export const MORATORIUM_CAPITALISE = 'capitalise'
export const MORATORIUM_SERVICE_INTEREST = 'service-interest'

/**
 * @param principal        loan amount in rupees (the amount actually disbursed)
 * @param annualRatePct    annual interest rate, e.g. 8 for 8%
 * @param tenureMonths     repayment tenure in months, counted AFTER the moratorium
 * @param options.moratoriumMonths  months before EMIs begin (default 0)
 * @param options.moratoriumMode    MORATORIUM_CAPITALISE | MORATORIUM_SERVICE_INTEREST
 * @returns {{
 *   emi, totalPayment, totalInterest, moratoriumInterest, moratoriumPayment,
 *   financedPrincipal, moratoriumMonths, moratoriumMode, schedule
 * }}
 *   totalInterest is the full cost of credit measured against the disbursed
 *   principal — it includes anything accrued or paid during the moratorium.
 */
export function calculateEmi(principal, annualRatePct, tenureMonths, options = {}) {
  const {
    moratoriumMonths = 0,
    moratoriumMode = MORATORIUM_CAPITALISE,
  } = options

  const p = Math.max(0, Number(principal) || 0)
  const n = Math.max(1, Math.round(Number(tenureMonths) || 1))
  const m = Math.max(0, Math.round(Number(moratoriumMonths) || 0))
  const monthlyRate = (Number(annualRatePct) || 0) / 12 / 100

  const servicing = moratoriumMode === MORATORIUM_SERVICE_INTEREST

  // What the EMI is actually computed against. Under capitalisation the
  // moratorium's accrued interest joins the principal; under interest-
  // servicing it has already been paid, so the principal is untouched.
  const financedPrincipal = servicing ? p : p * Math.pow(1 + monthlyRate, m)

  // Interest that accrued during the moratorium, either way — this is the
  // figure the old implementation dropped entirely.
  const moratoriumInterest = servicing
    ? p * monthlyRate * m
    : financedPrincipal - p
  // ...and what the citizen actually hands over during those months.
  const moratoriumPayment = servicing ? moratoriumInterest : 0

  const emi = monthlyRate === 0
    ? financedPrincipal / n
    : (() => {
        const factor = Math.pow(1 + monthlyRate, n)
        return (financedPrincipal * monthlyRate * factor) / (factor - 1)
      })()

  const totalPayment = moratoriumPayment + emi * n
  const totalInterest = totalPayment - p

  return {
    emi,
    totalPayment,
    totalInterest,
    moratoriumInterest,
    moratoriumPayment,
    financedPrincipal,
    moratoriumMonths: m,
    moratoriumMode,
    schedule: buildSchedule(p, financedPrincipal, monthlyRate, emi, n, m, servicing),
  }
}

/**
 * Absolute month numbering across the whole loan life — moratorium months are
 * 1..m and repayment runs m+1..m+n. Each row carries `phase` so the UI can
 * render the two stretches distinctly instead of implying EMIs start at month 1.
 */
function buildSchedule(principal, financedPrincipal, monthlyRate, emi, n, m, servicing) {
  const rows = []
  let balance = principal

  for (let month = 1; month <= m; month++) {
    const interestComponent = balance * monthlyRate
    if (!servicing) balance += interestComponent // capitalised into the principal
    rows.push({
      month,
      phase: 'moratorium',
      emi: servicing ? interestComponent : 0,
      principalComponent: 0,
      interestComponent,
      balance,
    })
  }

  balance = financedPrincipal
  for (let i = 1; i <= n; i++) {
    const interestComponent = balance * monthlyRate
    const principalComponent = emi - interestComponent
    balance = Math.max(0, balance - principalComponent)
    rows.push({
      month: m + i,
      phase: 'repayment',
      emi,
      principalComponent,
      interestComponent,
      balance,
    })
  }

  return rows
}

export function formatInr(amount) {
  return '₹' + Math.round(amount).toLocaleString('en-IN')
}
