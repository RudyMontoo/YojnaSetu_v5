// NSFDC-style concessional credit & education loan schemes for the SC
// community, structured directly from the SIH problem statement's own
// stated parameters (income ceiling, loan caps, rate range, moratorium
// range). These are REPRESENTATIVE figures for this module's demo, not
// scraped from a live nsfdc.nic.in source — verify exact current rates/caps
// against the official NSFDC scheme pages before treating this as
// authoritative for a real citizen's application.

export const NSFDC_SCHEMES = [
  {
    id: "micro-finance",
    name: "Micro Finance Scheme (MFS)",
    forProjectType: "small",
    maxLoanAmount: 140000,      // ₹1.40 lakh cap, per problem statement
    minLoanAmount: 5000,
    interestRate: 6.5,          // % per annum, concessional band
    moratoriumMonths: 3,
    maxTenureMonths: 36,
    coveragePct: 90,            // up to 90% of project cost financed
    description: "For small income-generating projects — petty trade, small crafts, micro-enterprise setup.",
  },
  {
    id: "term-loan",
    name: "Term Loan Scheme",
    forProjectType: "large",
    maxLoanAmount: 5000000,     // ₹50 lakh cap, per problem statement
    minLoanAmount: 140001,      // starts where Micro Finance caps out
    interestRate: 8,
    moratoriumMonths: 6,
    maxTenureMonths: 84,
    coveragePct: 90,
    description: "For larger self-employment or business expansion projects needing more capital than the Micro Finance Scheme covers.",
  },
  {
    id: "education-loan",
    name: "Educational Loan Scheme",
    forProjectType: "education",
    maxLoanAmount: 2000000,     // representative cap for full course + related costs
    minLoanAmount: 10000,
    interestRate: 6.5,
    moratoriumMonths: 12,       // full course duration + a grace period is typical for education loans
    maxTenureMonths: 120,
    coveragePct: 90,
    description: "Covers tuition, hostel, and related costs for professional/technical courses in India or abroad.",
  },
];

export const INCOME_CEILING = 500000; // ₹5 lakh annual family income eligibility ceiling

/**
 * Smart Scheme Recommender — rule-based, per the SIH brief ("AI/rule-based
 * engine"). Takes the citizen's stated inputs and returns the best-fit
 * scheme(s), most-suitable first. Deliberately simple and auditable: every
 * rule below can be read back to a citizen as a plain reason.
 */
export function recommendScheme({ projectType, estimatedCost, annualIncome, isEducation }) {
  if (annualIncome != null && annualIncome > INCOME_CEILING) {
    return {
      eligible: false,
      reason: `Annual family income of ₹${annualIncome.toLocaleString("en-IN")} exceeds the ₹${INCOME_CEILING.toLocaleString("en-IN")} eligibility ceiling for these concessional schemes.`,
      schemes: [],
    };
  }

  const cost = Number(estimatedCost) || 0;
  let candidates;

  if (isEducation || projectType === "education") {
    candidates = NSFDC_SCHEMES.filter((s) => s.forProjectType === "education");
  } else if (cost <= 140000) {
    candidates = NSFDC_SCHEMES.filter((s) => s.forProjectType === "small");
  } else {
    candidates = NSFDC_SCHEMES.filter((s) => s.forProjectType === "large");
  }

  const ranked = candidates.map((s) => ({
    ...s,
    matchReason: isEducation || projectType === "education"
      ? "Matched on project type: education."
      : cost <= 140000
        ? `Matched on estimated cost (₹${cost.toLocaleString("en-IN")}) fitting within the Micro Finance cap of ₹1.40 lakh.`
        : `Matched on estimated cost (₹${cost.toLocaleString("en-IN")}) exceeding the Micro Finance cap, routed to Term Loan.`,
  }));

  return { eligible: true, reason: null, schemes: ranked };
}
