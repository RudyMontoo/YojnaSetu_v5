package com.yojnasetu.gateway.controller;

import com.yojnasetu.gateway.model.Scheme;
import com.yojnasetu.gateway.repository.SchemeRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.List;
import java.util.Optional;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * GET /api/v2/schemes/{schemeCode} — the public scheme-detail lookup added
 * so a scheme page is reachable directly (a shared link, a bookmark, a
 * fresh load) rather than only via router state carried from the list page
 * in the same browser session. {@link #listSchemes} itself uses raw
 * MongoTemplate queries not covered here — this pins only the new
 * repository-backed detail endpoint.
 */
class SchemeCatalogueControllerMvcTest {

    private MockMvc mvc;
    private SchemeRepository schemes;

    @BeforeEach
    void setUp() {
        schemes = mock(SchemeRepository.class);
        SchemeCatalogueController controller = new SchemeCatalogueController(mock(MongoTemplate.class), schemes);
        mvc = MockMvcBuilders.standaloneSetup(controller)
                .setMessageConverters(new MappingJackson2HttpMessageConverter())
                .build();
    }

    private static Scheme scheme() {
        Scheme s = new Scheme();
        s.setId("mongo-object-id-should-never-appear");
        s.setSchemeCode("PM-KISAN");
        s.setName("PM Kisan Samman Nidhi");
        s.setMinistry("Ministry of Agriculture");
        s.setState(null);
        s.setSector("Agriculture");
        s.setCategory(List.of("farmer"));
        s.setEligibilityText("Small and marginal farmer families");
        s.setBenefitAmount("₹6,000/year");
        s.setDocuments(List.of("Aadhaar", "Land record"));
        s.setApplyUrl("https://pmkisan.gov.in");
        return s;
    }

    @Test
    void returnsTheFullPublicRecordByCode() throws Exception {
        when(schemes.findBySchemeCode("PM-KISAN")).thenReturn(Optional.of(scheme()));

        mvc.perform(get("/api/v2/schemes/PM-KISAN"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.schemeCode").value("PM-KISAN"))
                .andExpect(jsonPath("$.name").value("PM Kisan Samman Nidhi"))
                .andExpect(jsonPath("$.eligibilityText").value("Small and marginal farmer families"))
                .andExpect(jsonPath("$.benefitAmount").value("₹6,000/year"))
                .andExpect(jsonPath("$.documents[0]").value("Aadhaar"))
                .andExpect(jsonPath("$.id").doesNotExist());
    }

    @Test
    void returnsNotFoundForAnUnknownCode() throws Exception {
        when(schemes.findBySchemeCode("GHOST")).thenReturn(Optional.empty());

        mvc.perform(get("/api/v2/schemes/GHOST"))
                .andExpect(status().isNotFound());
    }
}
