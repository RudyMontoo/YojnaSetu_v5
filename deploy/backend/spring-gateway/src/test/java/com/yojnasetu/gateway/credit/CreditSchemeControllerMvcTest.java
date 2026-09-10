package com.yojnasetu.gateway.credit;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Optional;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Exercises CreditSchemeController through real Spring MVC binding — JSON
 * parsing, enum conversion, HTTP status mapping — rather than calling its
 * methods directly. That distinction is the point: every unit test on
 * EligibilityRequest and MoratoriumMode passed while this layer had a real bug
 * in it (see WireEnumConvertersTest).
 */
class CreditSchemeControllerMvcTest {

    private MockMvc mvc;
    private CreditProductRepository products;
    private final ObjectMapper json = new ObjectMapper();

    @BeforeEach
    void setUp() {
        products = mock(CreditProductRepository.class);
        when(products.findByActiveTrue()).thenReturn(List.of(microFinance()));
        when(products.findById(anyString())).thenReturn(Optional.empty());

        CreditEligibilityService eligibility = new CreditEligibilityService(products);
        CreditSchemeController controller = new CreditSchemeController(products, eligibility);
        mvc = MvcTestSupport.mvc(controller);
    }

    private static CreditProduct microFinance() {
        CreditProduct p = new CreditProduct();
        p.setId("micro-finance");
        p.setCode("MFS");
        p.setName("Micro Finance Scheme (MFS)");
        p.setType("micro");
        p.setProjectType("small");
        p.setUnitCostCeiling(140_000L);
        p.setMaxLoanAmount(125_000L);
        p.setInterestRate(6.5);
        p.setMoratoriumMonths(3);
        p.setMaxTenureMonths(36);
        p.setCoveragePct(90);
        p.setMaxAnnualIncome(500_000L);
        p.setCategories(List.of("sc"));
        p.setActive(true);
        return p;
    }

    @Test
    void listsTheCatalogue() throws Exception {
        mvc.perform(get("/api/v2/sih/credit/products"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].id").value("micro-finance"))
                .andExpect(jsonPath("$[0].interestRate").value(6.5));
    }

    @Test
    void evaluatesEligibilityFromARealJsonBody() throws Exception {
        // Fixture has one product and it is not women-only, so gender is not a
        // question this catalogue needs answered — asserting "eligible" here,
        // not "insufficient_data", is deliberate: an eligibility test suite
        // once passed in full against a fixture that silently drifted from the
        // real seeded catalogue (CreditEligibilityServiceTest vs
        // CreditEligibilityRealCatalogueTest). This file is intentionally
        // narrow — it proves the HTTP layer parses and routes correctly; the
        // real catalogue's ranking and gender-gating are that other file's job.
        String body = """
                {"need":"business","estimatedCost":100000,"annualIncome":300000,
                 "category":"sc","gender":"female"}""";

        mvc.perform(post("/api/v2/sih/credit/eligibility")
                        .contentType("application/json").content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.verdict").value("eligible"))
                .andExpect(jsonPath("$.recommendations[0].productId").value("micro-finance"));
    }

    @Test
    void rejectsEligibilityWithNoNeed() throws Exception {
        mvc.perform(post("/api/v2/sih/credit/eligibility")
                        .contentType("application/json").content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").exists());
    }

    @Test
    void rejectsNegativeIncome() throws Exception {
        String body = """
                {"need":"business","estimatedCost":100000,"annualIncome":-1,"category":"sc"}""";
        mvc.perform(post("/api/v2/sih/credit/eligibility")
                        .contentType("application/json").content(body))
                .andExpect(status().isBadRequest());
    }

    @Test
    void parsesMoratoriumModeFromTheJsonBody() throws Exception {
        // The spelling the frontend exports — this is the half of the split
        // that always worked, kept here so a regression on either half shows up.
        String body = """
                {"need":"business","estimatedCost":100000,"annualIncome":300000,
                 "category":"sc","gender":"male","moratoriumMode":"service-interest"}""";

        mvc.perform(post("/api/v2/sih/credit/eligibility")
                        .contentType("application/json").content(body))
                .andExpect(status().isOk());
    }

    @Test
    void quotesAnEmiFromARealJsonBody() throws Exception {
        String body = """
                {"principal":90000,"annualRatePct":6.5,"tenureMonths":36,
                 "moratoriumMonths":3,"moratoriumMode":"capitalise"}""";

        mvc.perform(post("/api/v2/sih/credit/emi")
                        .contentType("application/json").content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.moratoriumMonths").value(3))
                .andExpect(jsonPath("$.schedule[0].phase").value("moratorium"))
                .andExpect(jsonPath("$.schedule[0].emi").value(0.0));
    }

    @Test
    void rejectsAnUnknownMoratoriumModeInTheBody() throws Exception {
        String body = """
                {"principal":90000,"annualRatePct":6.5,"tenureMonths":36,
                 "moratoriumMode":"interest-free"}""";

        // Confirms the /error 400-vs-403 fix (SecurityConfig) has nothing to do
        // with this layer — a malformed enum in a body is a plain 400 here too.
        mvc.perform(post("/api/v2/sih/credit/emi")
                        .contentType("application/json").content(body))
                .andExpect(status().isBadRequest());
    }

    @Test
    void rejectsAPrincipalOverTheQuotableCeiling() throws Exception {
        String body = """
                {"principal":999999999999,"annualRatePct":6.5,"tenureMonths":36}""";
        mvc.perform(post("/api/v2/sih/credit/emi")
                        .contentType("application/json").content(body))
                .andExpect(status().isBadRequest());
    }

    @Test
    void rejectsATenureOfZero() throws Exception {
        String body = """
                {"principal":90000,"annualRatePct":6.5,"tenureMonths":0}""";
        mvc.perform(post("/api/v2/sih/credit/emi")
                        .contentType("application/json").content(body))
                .andExpect(status().isBadRequest());
    }
}
