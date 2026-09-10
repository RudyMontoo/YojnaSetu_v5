package com.yojnasetu.gateway.credit;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.util.List;

/**
 * A concessional credit or education-loan product a citizen can be matched to
 * — the NSFDC schemes behind SIH PS 26092.
 *
 * These parameters previously lived in a hardcoded array in the frontend
 * bundle, which meant the eligibility ceiling was enforced in the browser
 * (trivially bypassable) and a rate change needed a frontend deploy. They are
 * server-side now: this collection is the single source of truth, and the
 * browser renders what it is told.
 *
 * PROVENANCE: the seeded figures are structured from the SIH problem
 * statement's own stated parameters (income ceiling, loan caps, rate band,
 * moratorium range). They are representative for this module, NOT scraped from
 * a live nsfdc.nic.in feed — {@link #sourceNote} carries that caveat per
 * product so it can be surfaced to a citizen rather than buried in a comment.
 */
@Document(collection = "credit_products")
@Data
@NoArgsConstructor
public class CreditProduct {

    /** Stable slug, e.g. "micro-finance" — referenced by applications. */
    @Id
    private String id;

    /** Short official code, e.g. "MFS". */
    private String code;

    private String name;

    /** micro | term | education */
    private String type;

    /**
     * Which kind of need this funds: {@code small}, {@code large} or
     * {@code education}. Drives matching in CreditEligibilityService.
     */
    @Indexed
    private String projectType;

    /**
     * Smallest project NSFDC will consider under this scheme, by UNIT COST —
     * null when there is no floor. Term Loan starts at ₹1,40,001 precisely
     * because Micro Finance covers everything below it.
     */
    private Long unitCostFloor;

    /**
     * Largest project cost the scheme covers, null when uncapped (the
     * Educational Loan is bounded by its loan ceiling, not by a course-fee
     * limit).
     *
     * This is NOT the loan amount and the two must not be conflated: Micro
     * Finance covers units costing up to ₹1.40 lakh but lends at most ₹1.25
     * lakh. Treating the unit-cost ceiling as the loan cap overstates what a
     * citizen can borrow by ₹15,000 and hides the margin money they owe.
     */
    private Long unitCostCeiling;

    /** Hard ceiling on the loan itself, after coveragePct is applied. */
    private long maxLoanAmount;

    /** Annual percentage rate, e.g. 6.5. */
    private double interestRate;

    private int moratoriumMonths;
    private int maxTenureMonths;

    /**
     * Share of project cost the loan can finance, e.g. 90. The remainder is the
     * citizen's own margin-money contribution — the most common practical
     * reason these applications stall, so it is modelled rather than displayed
     * as decoration.
     */
    private int coveragePct;

    /** Annual family income ceiling in rupees. Enforced server-side. */
    private long maxAnnualIncome;

    /** Social categories eligible for this product, lowercase, e.g. ["sc"]. */
    private List<String> categories;

    /**
     * True for the women-only schemes (Mahila Samriddhi Yojana and its
     * siblings), which carry a materially lower beneficiary rate.
     *
     * NSFDC delivers the women's concession as separate schemes rather than as
     * a discount on a general one, so this is a filter on who the product is
     * for — not a second rate hanging off another product. It also means
     * {@code gender} becomes a real eligibility criterion: without it we cannot
     * tell whether a woman applicant is being offered her best available rate.
     */
    private boolean womenOnly;

    /**
     * Which kinds of institution can actually deliver this scheme.
     *
     * The interest rate on this product is the one charged by these partner
     * types — NSFDC funds the partner at a lower rate and the partner sets the
     * beneficiary rate, so an identical scheme costs differently through a
     * different channel. Micro-finance is 6.5% via an SCA and 15% via an
     * NBFC-MFI, which is why the locator filters on this rather than showing
     * every bank within 15km.
     */
    private List<ChannelPartnerType> channelPartnerTypes;

    private String description;

    /** Where these figures came from, and how far they can be trusted. */
    private String sourceNote;

    /** The page the figures were read from, so anyone can re-check them. */
    private String sourceUrl;

    /**
     * False when the figures come from a secondary source rather than NSFDC's
     * own scheme page. Surface it — an unverified rate is still worth showing,
     * but not worth presenting as settled.
     */
    private boolean figuresVerified;

    private boolean active = true;
}
