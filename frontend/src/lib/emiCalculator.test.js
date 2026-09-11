import { describe, it, expect } from 'vitest'
import {
  calculateEmi,
  formatInr,
  MORATORIUM_CAPITALISE,
  MORATORIUM_SERVICE_INTEREST,
} from './emiCalculator'

// The Micro Finance Scheme's real parameters, as served by the backend
// catalogue (GET /api/v2/sih/credit/products).
//
// The principal here was 140000, copied from the old hardcoded
// lib/nsfdcSchemes.js — but ₹1.40 lakh is the scheme's PROJECT-COST ceiling,
// not its loan cap, which is ₹1.25 lakh. Only the EMI maths is under test so
// the assertions held either way, but leaving the wrong number labelled "the
// Micro Finance Scheme's real parameters" is how that figure kept spreading.
const MFS = { principal: 125000, rate: 6.5, tenure: 36, moratorium: 3 }

const near = (a, b, tolerance = 0.01) => expect(Math.abs(a - b)).toBeLessThan(tolerance)

describe('calculateEmi — no moratorium', () => {
  it('matches the standard reducing-balance formula', () => {
    const { emi } = calculateEmi(100000, 12, 12)
    // P·r·(1+r)^n / ((1+r)^n − 1) with r = 0.01
    const r = 0.01
    const f = Math.pow(1 + r, 12)
    near(emi, (100000 * r * f) / (f - 1))
  })

  it('handles a zero interest rate as a straight principal split', () => {
    const { emi, totalInterest, totalPayment } = calculateEmi(120000, 0, 12)
    near(emi, 10000)
    near(totalInterest, 0)
    near(totalPayment, 120000)
  })

  it('is unchanged when called with the old three-argument signature', () => {
    // Guards the existing callers: omitting options must mean "no moratorium".
    const threeArg = calculateEmi(140000, 6.5, 36)
    const explicit = calculateEmi(140000, 6.5, 36, { moratoriumMonths: 0 })
    near(threeArg.emi, explicit.emi)
    near(threeArg.totalPayment, explicit.totalPayment)
    expect(threeArg.schedule).toHaveLength(36)
  })
})

describe('calculateEmi — capitalised moratorium', () => {
  const result = calculateEmi(MFS.principal, MFS.rate, MFS.tenure, {
    moratoriumMonths: MFS.moratorium,
    moratoriumMode: MORATORIUM_CAPITALISE,
  })

  it('capitalises accrued interest into the principal', () => {
    // 125000 × (1 + 0.065/12)^3
    near(result.financedPrincipal, 127042.27, 0.05)
    near(result.moratoriumInterest, 2042.27, 0.05)
  })

  it('collects nothing from the citizen during the moratorium', () => {
    near(result.moratoriumPayment, 0)
    for (const row of result.schedule.filter((r) => r.phase === 'moratorium')) {
      near(row.emi, 0)
      near(row.principalComponent, 0)
      expect(row.interestComponent).toBeGreaterThan(0)
    }
  })

  it('costs strictly more than the same loan with no moratorium', () => {
    // This is the regression the old implementation shipped: it returned the
    // no-moratorium figure while the UI claimed a moratorium was in effect.
    const noMoratorium = calculateEmi(MFS.principal, MFS.rate, MFS.tenure)
    expect(result.totalInterest).toBeGreaterThan(noMoratorium.totalInterest)
    expect(result.emi).toBeGreaterThan(noMoratorium.emi)
  })
})

describe('calculateEmi — interest-servicing moratorium', () => {
  const result = calculateEmi(MFS.principal, MFS.rate, MFS.tenure, {
    moratoriumMonths: MFS.moratorium,
    moratoriumMode: MORATORIUM_SERVICE_INTEREST,
  })

  it('leaves the principal untouched', () => {
    near(result.financedPrincipal, MFS.principal)
  })

  it('charges simple interest for each moratorium month', () => {
    const monthly = MFS.principal * (MFS.rate / 12 / 100)
    near(result.moratoriumInterest, monthly * MFS.moratorium)
    near(result.moratoriumPayment, monthly * MFS.moratorium)
    for (const row of result.schedule.filter((r) => r.phase === 'moratorium')) {
      near(row.emi, monthly)
      near(row.balance, MFS.principal)
    }
  })

  it('keeps the EMI identical to the no-moratorium loan', () => {
    const noMoratorium = calculateEmi(MFS.principal, MFS.rate, MFS.tenure)
    near(result.emi, noMoratorium.emi)
  })

  it('costs less overall than capitalising', () => {
    const capitalised = calculateEmi(MFS.principal, MFS.rate, MFS.tenure, {
      moratoriumMonths: MFS.moratorium,
      moratoriumMode: MORATORIUM_CAPITALISE,
    })
    expect(result.totalPayment).toBeLessThan(capitalised.totalPayment)
  })
})

describe('schedule integrity', () => {
  for (const mode of [MORATORIUM_CAPITALISE, MORATORIUM_SERVICE_INTEREST]) {
    describe(mode, () => {
      const result = calculateEmi(MFS.principal, MFS.rate, MFS.tenure, {
        moratoriumMonths: MFS.moratorium,
        moratoriumMode: mode,
      })

      it('spans the whole loan life with absolute month numbers', () => {
        expect(result.schedule).toHaveLength(MFS.moratorium + MFS.tenure)
        expect(result.schedule.map((r) => r.month)).toEqual(
          Array.from({ length: MFS.moratorium + MFS.tenure }, (_, i) => i + 1),
        )
        // The moratorium is the opening stretch, not an afterthought.
        expect(result.schedule.slice(0, MFS.moratorium).every((r) => r.phase === 'moratorium')).toBe(true)
        expect(result.schedule.slice(MFS.moratorium).every((r) => r.phase === 'repayment')).toBe(true)
      })

      it('amortises to a zero balance', () => {
        near(result.schedule.at(-1).balance, 0)
      })

      it('reconciles row-level interest against the reported total', () => {
        const summed = result.schedule.reduce((acc, r) => acc + r.interestComponent, 0)
        near(summed, result.totalInterest, 0.02)
      })
    })
  }
})

describe('education loan — the longest moratorium in the catalogue', () => {
  it('accrues twelve months of interest before the first EMI', () => {
    const { financedPrincipal, moratoriumInterest, schedule } = calculateEmi(2000000, 6.5, 120, {
      moratoriumMonths: 12,
      moratoriumMode: MORATORIUM_CAPITALISE,
    })
    near(financedPrincipal, 2000000 * Math.pow(1 + 0.065 / 12, 12), 0.05)
    expect(moratoriumInterest).toBeGreaterThan(130000)
    expect(schedule.filter((r) => r.phase === 'moratorium')).toHaveLength(12)
  })
})

describe('formatInr', () => {
  it('renders whole rupees in the Indian digit grouping', () => {
    expect(formatInr(140000)).toBe('₹1,40,000')
    expect(formatInr(2287.35)).toBe('₹2,287')
  })
})
