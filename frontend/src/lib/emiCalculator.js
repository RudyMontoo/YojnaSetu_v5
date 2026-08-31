// Standard reducing-balance EMI math — the same formula every bank uses.
// No external data dependency; the scheme-specific rate/moratorium/cap
// inputs come from nsfdcSchemes.js.

/**
 * @param principal   loan amount in rupees
 * @param annualRatePct   annual interest rate, e.g. 8 for 8%
 * @param tenureMonths    total repayment tenure in months (after moratorium)
 * @returns { emi, totalPayment, totalInterest, schedule }
 */
export function calculateEmi(principal, annualRatePct, tenureMonths) {
  const p = Number(principal) || 0;
  const n = Math.max(1, Math.round(Number(tenureMonths) || 1));
  const monthlyRate = (Number(annualRatePct) || 0) / 12 / 100;

  if (monthlyRate === 0) {
    const emi = p / n;
    return {
      emi,
      totalPayment: p,
      totalInterest: 0,
      schedule: buildSchedule(p, 0, emi, n),
    };
  }

  const factor = Math.pow(1 + monthlyRate, n);
  const emi = (p * monthlyRate * factor) / (factor - 1);
  const totalPayment = emi * n;
  const totalInterest = totalPayment - p;

  return {
    emi,
    totalPayment,
    totalInterest,
    schedule: buildSchedule(p, monthlyRate, emi, n),
  };
}

function buildSchedule(principal, monthlyRate, emi, n) {
  let balance = principal;
  const rows = [];
  for (let month = 1; month <= n; month++) {
    const interestComponent = balance * monthlyRate;
    const principalComponent = emi - interestComponent;
    balance = Math.max(0, balance - principalComponent);
    rows.push({
      month,
      emi,
      principalComponent,
      interestComponent,
      balance,
    });
  }
  return rows;
}

export function formatInr(amount) {
  return "₹" + Math.round(amount).toLocaleString("en-IN");
}
