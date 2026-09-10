package com.yojnasetu.gateway.credit;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.mockito.ArgumentCaptor;

import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Pins the seeded NSFDC figures against the source they were read from
 * (nsfdc.nic.in/scheme, 2026-09-10).
 *
 * This exists because the previous catalogue was wrong in a way no test would
 * have caught: it used each scheme's unit-cost ceiling as its maximum loan.
 * Encoding the real numbers here means a future edit that reintroduces that
 * conflation fails rather than quietly overstating what a citizen can borrow.
 */
class CreditProductSeederTest {

    private CreditProductRepository repository;
    private Map<String, CreditProduct> seeded;

    @BeforeEach
    void setUp() {
        repository = mock(CreditProductRepository.class);
        when(repository.existsById(anyString())).thenReturn(false);

        new CreditProductSeeder(repository).run();

        ArgumentCaptor<CreditProduct> captor = ArgumentCaptor.forClass(CreditProduct.class);
        verify(repository, atLeastOnce()).save(captor.capture());
        seeded = captor.getAllValues().stream()
                .collect(Collectors.toMap(CreditProduct::getId, Function.identity()));
    }

    private CreditProduct product(String id) {
        CreditProduct p = seeded.get(id);
        assertNotNull(p, () -> id + " was not seeded; catalogue is " + seeded.keySet());
        return p;
    }

    @Test
    void seedsTheSchemesTheProblemStatementIsAbout() {
        assertTrue(seeded.keySet().containsAll(List.of(
                        "micro-finance", "term-loan", "education-loan", "mahila-samriddhi")),
                () -> "missing core schemes; got " + seeded.keySet());
    }

    @Test
    void neverConfusesTheUnitCostCeilingWithTheMaximumLoan() {
        // The exact bug the old catalogue shipped. Micro Finance covers units up
        // to ₹1.40 lakh but lends at most ₹1.25 lakh — a ₹15,000 difference that
        // is the citizen's margin money, not extra borrowing.
        CreditProduct mfs = product("micro-finance");
        assertEquals(140_000L, mfs.getUnitCostCeiling());
        assertEquals(125_000L, mfs.getMaxLoanAmount());

        // Term Loan: units to ₹50 lakh, loan to ₹45 lakh.
        CreditProduct tl = product("term-loan");
        assertEquals(5_000_000L, tl.getUnitCostCeiling());
        assertEquals(4_500_000L, tl.getMaxLoanAmount());
    }

    @Test
    void startsTheTermLoanExactlyWhereMicroFinanceStops() {
        assertEquals(140_001L, product("term-loan").getUnitCostFloor());
        assertNull(product("micro-finance").getUnitCostFloor());
    }

    @Test
    void carriesTheOfficialBeneficiaryRates() {
        assertEquals(6.5, product("micro-finance").getInterestRate());
        assertEquals(8.0, product("term-loan").getInterestRate());
        assertEquals(6.5, product("education-loan").getInterestRate());
    }

    @Test
    void givesWomenAConcessionalRateBelowTheGeneralScheme() {
        CreditProduct msy = product("mahila-samriddhi");
        assertTrue(msy.isWomenOnly());
        assertTrue(msy.getInterestRate() < product("micro-finance").getInterestRate(),
                "the women's scheme must undercut the general one, or it has no purpose");
    }

    @Test
    void marksTheWomensSchemeFiguresAsUnverified() {
        // NSFDC's own scheme page does not publish MSY's beneficiary rate; 4%
        // comes from State Channelising Agency listings. Seeded, but never
        // presented as settled.
        assertFalse(product("mahila-samriddhi").isFiguresVerified());
        assertTrue(product("micro-finance").isFiguresVerified());
    }

    @Test
    void usesTheCurrentFiveLakhIncomeCeilingNotTheOldThreeLakhOne() {
        // Revised w.e.f. 07.01.2026. The scheme JSON in ai_service still carries
        // the superseded ₹3 lakh "double the poverty line" figure.
        seeded.values().forEach(p ->
                assertEquals(500_000L, p.getMaxAnnualIncome(), () -> p.getId() + " has the wrong ceiling"));
    }

    @ParameterizedTest
    @MethodSource("seededIds")
    void everyProductStatesWhereItsFiguresCameFrom(String id) {
        CreditProduct p = product(id);
        assertNotNull(p.getSourceNote(), () -> id + " has no source note");
        assertNotNull(p.getSourceUrl(), () -> id + " has no source URL");
        assertFalse(p.getSourceNote().isBlank());
    }

    @ParameterizedTest
    @MethodSource("seededIds")
    void everyProductIsInternallyConsistent(String id) {
        CreditProduct p = product(id);

        assertTrue(p.getMaxLoanAmount() > 0, () -> id + " lends nothing");
        assertTrue(p.getInterestRate() >= 0, () -> id + " has a negative rate");
        assertTrue(p.getMaxTenureMonths() > 0, () -> id + " has no tenure");
        assertTrue(p.getCoveragePct() > 0 && p.getCoveragePct() <= 100, () -> id + " has an impossible coverage");
        assertTrue(p.getMoratoriumMonths() >= 0, () -> id + " has a negative moratorium");

        if (p.getUnitCostFloor() != null && p.getUnitCostCeiling() != null) {
            assertTrue(p.getUnitCostFloor() < p.getUnitCostCeiling(),
                    () -> id + " has an inverted unit-cost band");
        }
        // A loan cap above what the scheme could ever lend on its own ceiling
        // would be unreachable — a sign the two figures got crossed again.
        if (p.getUnitCostCeiling() != null) {
            long mostItCouldLend = Math.round(p.getUnitCostCeiling() * (p.getCoveragePct() / 100.0));
            assertTrue(p.getMaxLoanAmount() <= mostItCouldLend,
                    () -> id + " caps the loan above 90% of its own unit-cost ceiling");
        }
    }

    static List<String> seededIds() {
        CreditProductRepository repo = mock(CreditProductRepository.class);
        when(repo.existsById(anyString())).thenReturn(false);
        new CreditProductSeeder(repo).run();
        ArgumentCaptor<CreditProduct> captor = ArgumentCaptor.forClass(CreditProduct.class);
        verify(repo, atLeastOnce()).save(captor.capture());
        return captor.getAllValues().stream().map(CreditProduct::getId).toList();
    }

    @Test
    void doesNotOverwriteFiguresSomeoneHasAlreadyCorrected() {
        CreditProductRepository existing = mock(CreditProductRepository.class);
        when(existing.existsById(anyString())).thenReturn(true);

        new CreditProductSeeder(existing).run();

        verify(existing, never()).save(any(CreditProduct.class));
    }
}
