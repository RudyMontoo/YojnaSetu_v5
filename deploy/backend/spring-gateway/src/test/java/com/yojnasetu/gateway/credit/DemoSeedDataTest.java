package com.yojnasetu.gateway.credit;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.mockito.ArgumentCaptor;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class DemoSeedDataTest {

    private CreditApplicationRepository applications;
    private BranchRepRepository branchReps;
    private CreditProductRepository products;
    private DemoSeedData seeder;

    @BeforeEach
    void setUp() {
        applications = mock(CreditApplicationRepository.class);
        branchReps = mock(BranchRepRepository.class);
        products = mock(CreditProductRepository.class);

        when(products.findById("micro-finance")).thenReturn(Optional.of(microFinance()));
        when(applications.existsById(anyString())).thenReturn(false);
        when(applications.save(any(CreditApplication.class))).thenAnswer(inv -> inv.getArgument(0));
        when(branchReps.findByRepId(anyString())).thenReturn(Optional.empty());

        seeder = new DemoSeedData(applications, branchReps, products);
    }

    private static CreditProduct microFinance() {
        CreditProduct p = new CreditProduct();
        p.setId("micro-finance");
        p.setCode("MFS");
        p.setName("Micro Finance Scheme (MFS)");
        p.setUnitCostCeiling(140_000L);
        p.setMaxLoanAmount(125_000L);
        p.setInterestRate(6.5);
        p.setMoratoriumMonths(3);
        p.setMaxTenureMonths(36);
        p.setCoveragePct(90);
        p.setActive(true);
        return p;
    }

    private void enable() {
        ReflectionTestUtils.setField(seeder, "enabled", true);
    }

    @Test
    void doesNothingWhenTheFlagIsOff() {
        seeder.run();
        verify(applications, never()).save(any());
        verify(branchReps, never()).save(any());
    }

    @Test
    void seedsExactlyOneApplicationPerStatus() {
        enable();
        seeder.run();

        ArgumentCaptor<CreditApplication> captor = ArgumentCaptor.forClass(CreditApplication.class);
        verify(applications, atLeastOnce()).save(captor.capture());

        Map<CreditApplicationStatus, Long> byStatus = captor.getAllValues().stream()
                .collect(Collectors.groupingBy(CreditApplication::getStatus, Collectors.counting()));

        for (CreditApplicationStatus status : CreditApplicationStatus.values()) {
            assertEquals(1L, byStatus.get(status), () -> "expected exactly one " + status);
        }
    }

    @Test
    void seedsABranchRepThatCanLogIn() {
        enable();
        seeder.run();

        ArgumentCaptor<BranchRep> captor = ArgumentCaptor.forClass(BranchRep.class);
        verify(branchReps).save(captor.capture());

        BranchRep rep = captor.getValue();
        assertNotNull(rep.getRepId());
        assertNotNull(rep.getPasswordHash());
        assertTrue(rep.isActive());
        assertFalse(rep.isMustResetPassword(), "a demo login should not interrupt the walkthrough");
    }

    @Test
    void skipsWhatIsAlreadyThereRatherThanDuplicating() {
        when(applications.existsById(anyString())).thenReturn(true);
        when(branchReps.findByRepId(anyString())).thenReturn(Optional.of(new BranchRep()));
        enable();

        seeder.run();

        verify(applications, never()).save(any());
        verify(branchReps, never()).save(any());
    }

    @Test
    void doesNotDuplicateOnASecondRun() {
        enable();
        // First run: nothing exists yet.
        seeder.run();

        // Second run: everything now exists.
        when(applications.existsById(anyString())).thenReturn(true);
        when(branchReps.findByRepId(anyString())).thenReturn(Optional.of(new BranchRep()));
        seeder.run();

        // Exactly 8 applications total across both runs, not 16.
        verify(applications, org.mockito.Mockito.times(8)).save(any());
    }

    @Test
    void refusesToSeedWithoutTheSchemeItDependsOn() {
        when(products.findById("micro-finance")).thenReturn(Optional.empty());
        enable();

        seeder.run();

        verify(applications, never()).save(any());
    }

    @Test
    void assignsAPartnerToEveryNonDraftApplication() {
        enable();
        seeder.run();

        ArgumentCaptor<CreditApplication> captor = ArgumentCaptor.forClass(CreditApplication.class);
        verify(applications, atLeastOnce()).save(captor.capture());

        for (CreditApplication app : captor.getAllValues()) {
            if (app.getStatus() == CreditApplicationStatus.DRAFT) {
                continue; // not yet submitted — nothing to assign
            }
            assertNotNull(app.getAssignedPartnerId(), () -> app.getStatus() + " has no partner");
        }
    }

    @Test
    void quotesRealMoratoriumCorrectTerms() {
        enable();
        seeder.run();

        ArgumentCaptor<CreditApplication> captor = ArgumentCaptor.forClass(CreditApplication.class);
        verify(applications, atLeastOnce()).save(captor.capture());

        CreditApplication any = captor.getAllValues().get(0);
        assertTrue(any.getQuotedTerms().getEmi() > 0);
        // The moratorium fix this whole module started with — a quote with a
        // moratorium set must show accrued interest, not a bare no-moratorium figure.
        assertTrue(any.getQuotedTerms().getTotalInterest() > 0);
    }

    @Test
    void aRejectedApplicationCarriesItsReasonCode() {
        enable();
        seeder.run();

        ArgumentCaptor<CreditApplication> captor = ArgumentCaptor.forClass(CreditApplication.class);
        verify(applications, atLeastOnce()).save(captor.capture());

        Map<CreditApplicationStatus, CreditApplication> byStatus = captor.getAllValues().stream()
                .collect(Collectors.toMap(CreditApplication::getStatus, Function.identity()));

        CreditApplication rejected = byStatus.get(CreditApplicationStatus.REJECTED);
        var lastEntry = rejected.getStatusHistory().get(rejected.getStatusHistory().size() - 1);
        assertEquals(ReasonCode.INCOME_ABOVE_CEILING, lastEntry.getReasonCode());
    }

    @Test
    void aMissingDocsApplicationNamesWhatWasAsked() {
        enable();
        seeder.run();

        ArgumentCaptor<CreditApplication> captor = ArgumentCaptor.forClass(CreditApplication.class);
        verify(applications, atLeastOnce()).save(captor.capture());

        CreditApplication missingDocs = captor.getAllValues().stream()
                .filter(a -> a.getStatus() == CreditApplicationStatus.MISSING_DOCS)
                .findFirst().orElseThrow();

        assertFalse(missingDocs.getMissingDocuments().isEmpty());
    }

    @ParameterizedTest
    @EnumSource(CreditApplicationStatus.class)
    void everyApplicationsHistoryEndsAtItsOwnStatus(CreditApplicationStatus target) {
        enable();
        seeder.run();

        ArgumentCaptor<CreditApplication> captor = ArgumentCaptor.forClass(CreditApplication.class);
        verify(applications, atLeastOnce()).save(captor.capture());

        CreditApplication app = captor.getAllValues().stream()
                .filter(a -> a.getStatus() == target)
                .findFirst().orElseThrow();

        List<CreditApplication.StatusEntry> history = app.getStatusHistory();
        assertFalse(history.isEmpty());
        assertEquals(target, history.get(history.size() - 1).getStatus());
        // The history is a real walk through the state machine, not a single
        // entry jumping straight to the target — worth demonstrating in a
        // timeline UI, which is the entire point of seeding this.
        if (target != CreditApplicationStatus.DRAFT) {
            assertTrue(history.size() > 1);
        }
    }

    @ParameterizedTest
    @EnumSource(CreditApplicationStatus.class)
    void everyHistoryStepIsALegalTransitionFromThePrevious(CreditApplicationStatus target) {
        enable();
        seeder.run();

        ArgumentCaptor<CreditApplication> captor = ArgumentCaptor.forClass(CreditApplication.class);
        verify(applications, atLeastOnce()).save(captor.capture());

        CreditApplication app = captor.getAllValues().stream()
                .filter(a -> a.getStatus() == target)
                .findFirst().orElseThrow();

        List<CreditApplication.StatusEntry> history = app.getStatusHistory();
        for (int i = 1; i < history.size(); i++) {
            CreditApplicationStatus from = history.get(i - 1).getStatus();
            CreditApplicationStatus to = history.get(i).getStatus();
            assertTrue(from.canMoveTo(to), () -> from + " -> " + to + " is not a legal transition");
        }
    }
}
