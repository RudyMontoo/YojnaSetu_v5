package com.yojnasetu.gateway.credit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Seeds NSFDC's credit products on first boot.
 *
 * SOURCE: figures read from NSFDC's own scheme listing at
 * https://nsfdc.nic.in/scheme (retrieved 2026-09-10), except Mahila Samriddhi
 * Yojana — see the note on that entry.
 *
 * These replace an earlier set inherited from the frontend bundle that was
 * wrong in two ways worth remembering: it used each scheme's UNIT COST ceiling
 * as the maximum loan (overstating Micro Finance borrowing by ₹15,000 and Term
 * Loan by ₹5 lakh), and it carried no women-only scheme at all despite 40% of
 * NSFDC's funds being earmarked for women.
 *
 * Insert-only: it fills gaps by id and never overwrites an existing document,
 * so a figure corrected against a fresher NSFDC circular is not reverted by the
 * next redeploy.
 */
@Component
public class CreditProductSeeder implements CommandLineRunner {

    private static final Logger LOG = LoggerFactory.getLogger(CreditProductSeeder.class);

    /**
     * Annual family income ceiling, revised to ₹5 lakh w.e.f. 07.01.2026 for
     * both rural and urban areas. The older ₹3 lakh "double the poverty line"
     * figure is superseded — the seed data in ai_service still carries it.
     */
    private static final long INCOME_CEILING = 500_000L;

    private static final List<String> SC_ONLY = List.of("sc");
    private static final String NSFDC_SCHEMES_URL = "https://nsfdc.nic.in/scheme";

    private static final String VERIFIED_NOTE =
            "Figures from NSFDC's official scheme listing (nsfdc.nic.in/scheme, retrieved "
                    + "2026-09-10). Rates and ceilings are revised periodically — the Channel "
                    + "Partner branch confirms the terms that actually apply to an application.";

    private final CreditProductRepository repository;

    public CreditProductSeeder(CreditProductRepository repository) {
        this.repository = repository;
    }

    @Override
    public void run(String... args) {
        int inserted = 0;
        for (CreditProduct product : catalogue()) {
            if (!repository.existsById(product.getId())) {
                repository.save(product);
                inserted++;
            }
        }
        if (inserted > 0) {
            LOG.info("Seeded {} credit product(s) into credit_products", inserted);
        }
    }

    private static List<CreditProduct> catalogue() {
        return List.of(
                // ---- self-employment ----
                // 6.5% is the SCA/CA beneficiary rate (NSFDC charges the agency
                // 2.5%). The same money through an NBFC-MFI is the Aajeevika
                // entry below at 15% — hence the channel list, which is what
                // stops the locator sending someone to the expensive door.
                builder("micro-finance", "MFS", "Micro Finance Scheme (MFS)", "micro", "small")
                        .unitCost(null, 140_000L).maxLoan(125_000L).rate(6.5)
                        .terms(3, 36)
                        .deliveredBy(ChannelPartnerType.SCA, ChannelPartnerType.PSB,
                                ChannelPartnerType.RRB, ChannelPartnerType.COOPERATIVE)
                        .describes("For small income-generating activities — petty trade, tea shops, "
                                + "candle or papad making, goat rearing, beauty parlours and similar.")
                        .build(),

                builder("term-loan", "TL", "Term Loan", "term", "large")
                        // Starts exactly where Micro Finance stops, so the two never overlap.
                        .unitCost(140_001L, 5_000_000L).maxLoan(4_500_000L).rate(8.0)
                        .terms(6, 84)
                        .deliveredBy(ChannelPartnerType.SCA, ChannelPartnerType.PSB,
                                ChannelPartnerType.RRB, ChannelPartnerType.COOPERATIVE)
                        .describes("For larger self-employment or business projects needing more "
                                + "capital than the Micro Finance Scheme covers.")
                        .build(),

                builder("udyam-nidhi", "UNY", "Udyam Nidhi Yojana (UNY)", "term", "large")
                        .unitCost(null, 500_000L).maxLoan(450_000L).rate(15.0)
                        .terms(3, 60)
                        .deliveredBy(ChannelPartnerType.COOPERATIVE, ChannelPartnerType.NBFC_MFI)
                        .describes("For small enterprise projects up to ₹5 lakh, routed through "
                                + "cooperative banks and small finance banks.")
                        .build(),

                builder("aajeevika-micro-finance", "AMFY", "Aajeevika Micro-Finance Yojana", "micro", "small")
                        .unitCost(null, 140_000L).maxLoan(125_000L).rate(15.0)
                        .terms(3, 36)
                        .deliveredBy(ChannelPartnerType.NBFC_MFI)
                        .describes("Micro-finance for livelihood activities, delivered through "
                                + "NBFC-MFI channel partners.")
                        .build(),

                // ---- women-only ----
                // The one entry NOT taken from NSFDC's own scheme listing: that page
                // does not publish MSY's beneficiary rate. Re-verified 2026-09-10
                // against secondary sources (paisabazaar.com, projectsarthi.com,
                // aimindia.in) — they agree NSFDC lends to the SCA at 2%, and the
                // SCA on-lends to the beneficiary at 6%, with a 3.5-year (42-month)
                // TOTAL loan life inclusive of the moratorium — i.e. 3 months
                // moratorium + 39 months of EMI, matching this class's
                // moratorium-is-separate-from-tenure convention (see
                // EmiCalculator's tenureMonths javadoc: "counted AFTER the
                // moratorium"). This resolves an earlier discrepancy: a 4% figure
                // exists too, but it belongs to Maharashtra's LIDCOM-administered
                // variant for the Charmakar community specifically, not the
                // national NSFDC scheme — using it here would have been the wrong
                // scheme's rate. Still flagged unverified because none of this
                // comes from NSFDC's own page and the moratorium's exact length
                // (vs. tenure-inclusive-of-it) isn't separately confirmed.
                builder("mahila-samriddhi", "MSY", "Mahila Samriddhi Yojana (MSY)", "micro", "small")
                        .unitCost(null, 140_000L).maxLoan(125_000L).rate(6.0)
                        .terms(3, 39)
                        .womenOnly()
                        .deliveredBy(ChannelPartnerType.SCA, ChannelPartnerType.COOPERATIVE)
                        .unverified("Unit cost follows NSFDC's micro-finance terms. The 6% beneficiary "
                                + "rate (NSFDC to SCA at 2%, SCA to beneficiary at 6%) and 3.5-year total "
                                + "loan life (3-month moratorium + 39-month repayment) come from secondary "
                                + "sources, not NSFDC's own scheme page — confirm both with the branch "
                                + "before relying on them. Do not confuse with the 4% rate quoted for "
                                + "Maharashtra's LIDCOM/Charmakar-community variant, which is a different, "
                                + "state-specific scheme.")
                        .describes("Micro-finance for women beneficiaries, individually or through "
                                + "Self-Help Groups, at a concessional rate.")
                        .build(),

                // ---- education ----
                builder("education-loan", "ELS", "Educational Loan Scheme (ELS)", "education", "education")
                        // No course-fee ceiling published; the loan cap is the binding constraint.
                        .unitCost(null, null).maxLoan(4_000_000L).rate(6.5)
                        .deliveredBy(ChannelPartnerType.SCA, ChannelPartnerType.PSB)
                        // NSFDC publishes repayment "up to 12 years"; the moratorium is the
                        // course period plus a grace, which varies by course, so the
                        // conventional 12 months is used as the quotable default.
                        .terms(12, 144)
                        .describes("Covers tuition and related costs for professional and technical "
                                + "courses in India or abroad, up to 90% of the course fee.")
                        .build());
    }

    // ------------------------------------------------------------------ builder

    private static Builder builder(String id, String code, String name, String type, String projectType) {
        return new Builder(id, code, name, type, projectType);
    }

    private static final class Builder {
        private final CreditProduct p = new CreditProduct();

        Builder(String id, String code, String name, String type, String projectType) {
            p.setId(id);
            p.setCode(code);
            p.setName(name);
            p.setType(type);
            p.setProjectType(projectType);
            p.setCoveragePct(90);
            p.setMaxAnnualIncome(INCOME_CEILING);
            p.setCategories(SC_ONLY);
            p.setSourceUrl(NSFDC_SCHEMES_URL);
            p.setSourceNote(VERIFIED_NOTE);
            p.setFiguresVerified(true);
            p.setActive(true);
        }

        Builder unitCost(Long floor, Long ceiling) {
            p.setUnitCostFloor(floor);
            p.setUnitCostCeiling(ceiling);
            return this;
        }

        Builder maxLoan(long amount) {
            p.setMaxLoanAmount(amount);
            return this;
        }

        Builder rate(double rate) {
            p.setInterestRate(rate);
            return this;
        }

        Builder terms(int moratoriumMonths, int maxTenureMonths) {
            p.setMoratoriumMonths(moratoriumMonths);
            p.setMaxTenureMonths(maxTenureMonths);
            return this;
        }

        Builder womenOnly() {
            p.setWomenOnly(true);
            return this;
        }

        Builder deliveredBy(ChannelPartnerType... types) {
            p.setChannelPartnerTypes(List.of(types));
            return this;
        }

        Builder unverified(String note) {
            p.setFiguresVerified(false);
            p.setSourceNote(note);
            return this;
        }

        Builder describes(String description) {
            p.setDescription(description);
            return this;
        }

        CreditProduct build() {
            return p;
        }
    }
}
