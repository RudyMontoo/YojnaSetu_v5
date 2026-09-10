package com.yojnasetu.gateway.credit;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Eligibility against the ACTUAL seeded catalogue rather than a hand-written
 * fixture.
 *
 * This class exists because a fixture lied. CreditEligibilityServiceTest seeds
 * four products; production seeds six. With gender unstated, Mahila Samriddhi
 * ranks below the three eligible schemes and fell outside the top-three cut —
 * and because missingProfileData was collected AFTER that cut, the request for
 * gender vanished and the response claimed "eligible" while quietly hiding the
 * 4% women's scheme from women entitled to it. Every unit test passed.
 *
 * Anything that depends on how many products exist, or on their relative
 * ranking, belongs here where the real catalogue is the input.
 */
class CreditEligibilityRealCatalogueTest {

    private CreditEligibilityService service;

    @BeforeEach
    void setUp() {
        CreditProductRepository seedSource = mock(CreditProductRepository.class);
        when(seedSource.existsById(anyString())).thenReturn(false);
        new CreditProductSeeder(seedSource).run();

        ArgumentCaptor<CreditProduct> captor = ArgumentCaptor.forClass(CreditProduct.class);
        verify(seedSource, atLeastOnce()).save(captor.capture());
        List<CreditProduct> realCatalogue = captor.getAllValues();

        CreditProductRepository repository = mock(CreditProductRepository.class);
        when(repository.findByActiveTrue()).thenReturn(realCatalogue);
        service = new CreditEligibilityService(repository);
    }

    private EligibilityResponse business(String gender) {
        return service.evaluate(new EligibilityRequest(
                EligibilityRequest.NEED_BUSINESS, 100_000L, 300_000L, "sc", gender, null));
    }

    @Test
    void asksForGenderEvenWhenTheApplicantAlreadyQualifiesForSomething() {
        // The regression. Eligible for Micro Finance, but gender is still the
        // question that could halve their interest rate — so it must be asked.
        EligibilityResponse response = business(null);

        assertTrue(response.missingProfileData().contains("gender"),
                () -> "gender must be asked; got " + response.missingProfileData());
    }

    @Test
    void saysWhyAnsweringIsWorthTheApplicantsTime() {
        assertTrue(business(null).note().contains("lower interest rate"),
                () -> "got: " + business(null).note());
    }

    @Test
    void collectsQuestionsFromProductsThatRankBelowTheDisplayedThree() {
        EligibilityResponse response = business(null);

        // Exactly the shape that broke: three shown, but a question gathered
        // from a product that isn't one of them.
        assertEquals(3, response.recommendations().size());
        assertTrue(response.recommendations().stream()
                .noneMatch(r -> r.productId().equals("mahila-samriddhi")));
        assertTrue(response.missingProfileData().contains("gender"));
    }

    @Test
    void leadsAWomanWithTheConcessionalScheme() {
        SchemeRecommendation top = business("female").recommendations().get(0);

        assertEquals("mahila-samriddhi", top.productId());
        assertEquals(4.0, top.interestRate());
        assertTrue(top.eligible());
    }

    @Test
    void quotesAWomanLessThanTheGeneralScheme() {
        double womens = business("female").recommendations().get(0).indicativeEmi().totalPayment();
        double general = business("male").recommendations().get(0).indicativeEmi().totalPayment();

        assertTrue(womens < general, () -> womens + " should be below " + general);
        // Live check on the seeded figures: ~₹4,300 on a ₹90,000 loan.
        assertTrue(general - womens > 4_000, () -> "saving was only " + (general - womens));
    }

    @Test
    void doesNotOfferTheWomensSchemeToAMan() {
        assertTrue(business("male").recommendations().stream()
                .noneMatch(r -> r.productId().equals("mahila-samriddhi")));
    }

    @Test
    void ranksByWhatTheLoanActuallyCostsNotJustTheHeadlineRate() {
        // Udyam Nidhi and Aajeevika both quote 15%. Aajeevika's shorter term
        // makes it materially cheaper, so it must not rank below.
        List<String> order = business("male").recommendations().stream()
                .map(SchemeRecommendation::productId)
                .toList();

        int aajeevika = order.indexOf("aajeevika-micro-finance");
        int udyam = order.indexOf("udyam-nidhi");
        if (aajeevika >= 0 && udyam >= 0) {
            assertTrue(aajeevika < udyam,
                    () -> "cheaper scheme should rank first, got " + order);
        }
    }

    @Test
    void ordersEveryRecommendationByAscendingCost() {
        List<SchemeRecommendation> shown = business("female").recommendations();

        for (int i = 1; i < shown.size(); i++) {
            double previous = shown.get(i - 1).indicativeEmi().totalPayment();
            double current = shown.get(i).indicativeEmi().totalPayment();
            int index = i;
            assertTrue(previous <= current,
                    () -> "recommendation " + index + " costs less than the one above it");
        }
    }

    @Test
    void routesATenLakhProjectToTheTermLoanOnly() {
        EligibilityResponse response = service.evaluate(new EligibilityRequest(
                EligibilityRequest.NEED_BUSINESS, 1_000_000L, 300_000L, "sc", "male", null));

        assertEquals("term-loan", response.recommendations().get(0).productId());
        assertTrue(response.recommendations().get(0).eligible());
    }

    @Test
    void refusesEveryoneOverTheIncomeCeiling() {
        EligibilityResponse response = service.evaluate(new EligibilityRequest(
                EligibilityRequest.NEED_BUSINESS, 100_000L, 600_000L, "sc", "female", null));

        assertEquals(EligibilityResponse.NOT_ELIGIBLE, response.verdict());
        assertTrue(response.recommendations().stream().noneMatch(SchemeRecommendation::eligible));
    }

    @Test
    void offersOnlyTheEducationLoanForACourse() {
        EligibilityResponse response = service.evaluate(new EligibilityRequest(
                EligibilityRequest.NEED_EDUCATION, 500_000L, 300_000L, "sc", "female", null));

        assertEquals(1, response.recommendations().size());
        assertEquals("education-loan", response.recommendations().get(0).productId());
        // No unit-cost ceiling on ELS, so a ₹5 lakh course is comfortably in band.
        assertFalse(response.recommendations().get(0).costExceedsCap());
    }
}
