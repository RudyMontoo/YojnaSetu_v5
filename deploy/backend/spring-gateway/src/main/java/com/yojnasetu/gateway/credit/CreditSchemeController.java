package com.yojnasetu.gateway.credit;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * The NSFDC credit module's read paths: the product catalogue, the eligibility
 * check, and repayment quotes.
 *
 * Deliberately unauthenticated, like the existing partner locator. A citizen
 * must be able to find out what they qualify for and what it would cost
 * BEFORE creating an account — putting that behind a login is exactly the
 * friction this platform exists to remove. Nothing here reads or writes a
 * profile; the inputs are whatever the caller types into the form, and no
 * response is persisted. Applications, which do carry identity, are a
 * separate authenticated surface.
 */
@RestController
@RequestMapping("/api/v2/sih/credit")
public class CreditSchemeController {

    /**
     * Loan amounts above this are rejected outright rather than fed to
     * Math.pow — a caller passing an absurd principal should get a clear 400,
     * not a schedule full of Infinity.
     */
    private static final long MAX_QUOTABLE_PRINCIPAL = 100_000_000L;
    private static final int MAX_TENURE_MONTHS = 480;
    private static final int MAX_MORATORIUM_MONTHS = 120;

    private final CreditProductRepository repository;
    private final CreditEligibilityService eligibilityService;

    public CreditSchemeController(CreditProductRepository repository,
                                  CreditEligibilityService eligibilityService) {
        this.repository = repository;
        this.eligibilityService = eligibilityService;
    }

    /** The catalogue the frontend renders, replacing its hardcoded copy. */
    @GetMapping("/products")
    public List<CreditProduct> products() {
        return repository.findByActiveTrue();
    }

    @PostMapping("/eligibility")
    public ResponseEntity<?> eligibility(@RequestBody EligibilityRequest request) {
        if (request == null || request.need() == null || request.need().isBlank()) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "need is required — one of: "
                            + EligibilityRequest.NEED_BUSINESS + ", " + EligibilityRequest.NEED_EDUCATION));
        }
        if (negative(request.estimatedCost()) || negative(request.annualIncome())) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "estimatedCost and annualIncome cannot be negative"));
        }
        return ResponseEntity.ok(eligibilityService.evaluate(request));
    }

    /**
     * A standalone repayment quote, for the calculator tab where the citizen
     * moves the amount and tenure themselves. The browser computes the same
     * figures live for slider responsiveness; this is the authoritative copy.
     */
    @PostMapping("/emi")
    public ResponseEntity<?> emi(@RequestBody EmiRequest request) {
        if (request == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "Request body is required"));
        }
        if (request.principal() == null || request.principal() <= 0
                || request.principal() > MAX_QUOTABLE_PRINCIPAL) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "principal must be between 1 and " + MAX_QUOTABLE_PRINCIPAL));
        }
        if (request.annualRatePct() == null || request.annualRatePct() < 0 || request.annualRatePct() > 100) {
            return ResponseEntity.badRequest().body(Map.of("error", "annualRatePct must be between 0 and 100"));
        }
        if (request.tenureMonths() == null || request.tenureMonths() < 1
                || request.tenureMonths() > MAX_TENURE_MONTHS) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "tenureMonths must be between 1 and " + MAX_TENURE_MONTHS));
        }
        int moratorium = request.moratoriumMonths() == null ? 0 : request.moratoriumMonths();
        if (moratorium < 0 || moratorium > MAX_MORATORIUM_MONTHS) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "moratoriumMonths must be between 0 and " + MAX_MORATORIUM_MONTHS));
        }

        return ResponseEntity.ok(EmiCalculator.calculate(
                request.principal(), request.annualRatePct(), request.tenureMonths(),
                moratorium,
                request.moratoriumMode() == null ? MoratoriumMode.CAPITALISE : request.moratoriumMode()));
    }

    private static boolean negative(Long value) {
        return value != null && value < 0;
    }

    public record EmiRequest(
            Long principal,
            Double annualRatePct,
            Integer tenureMonths,
            Integer moratoriumMonths,
            MoratoriumMode moratoriumMode) {
    }
}
