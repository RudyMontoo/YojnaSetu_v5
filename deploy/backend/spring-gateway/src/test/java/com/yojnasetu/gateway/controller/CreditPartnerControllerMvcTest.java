package com.yojnasetu.gateway.controller;

import com.yojnasetu.gateway.credit.CreditProduct;
import com.yojnasetu.gateway.credit.CreditProductRepository;
import com.yojnasetu.gateway.credit.PincodeGeocoder;
import com.yojnasetu.gateway.service.GeoLabelService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.format.support.DefaultFormattingConversionService;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.Optional;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Validation paths only — the success path makes a real HTTP call to
 * Overpass, which does not belong in a suite that runs on every push.
 * WireEnumConvertersTest already covers ConversionService generally; this
 * confirms schemeId's 400 behaviour without going near the network.
 */
class CreditPartnerControllerMvcTest {

    private MockMvc mvc;
    private CreditProductRepository products;

    @BeforeEach
    void setUp() {
        products = mock(CreditProductRepository.class);
        CreditPartnerController controller = new CreditPartnerController(
                mock(GeoLabelService.class), mock(PincodeGeocoder.class), products);
        mvc = MockMvcBuilders.standaloneSetup(controller)
                .setConversionService(new DefaultFormattingConversionService())
                .build();
    }

    @Test
    void requiresEitherCoordinatesOrAPincode() throws Exception {
        mvc.perform(get("/api/v2/credit-partners/nearby")).andExpect(status().isBadRequest());
    }

    @Test
    void rejectsAMalformedPincodeBeforeAnyLookup() throws Exception {
        mvc.perform(get("/api/v2/credit-partners/nearby").param("pincode", "0110")).
                andExpect(status().isBadRequest());
    }

    @Test
    void rejectsOutOfRangeCoordinates() throws Exception {
        mvc.perform(get("/api/v2/credit-partners/nearby")
                        .param("lat", "999").param("lng", "77"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void rejectsAnUnknownSchemeId() throws Exception {
        when(products.findById(anyString())).thenReturn(Optional.empty());

        mvc.perform(get("/api/v2/credit-partners/nearby")
                        .param("lat", "28.6").param("lng", "77.2").param("schemeId", "not-a-scheme"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void refusesAnInactiveSchemeAsIfItDoesNotExist() throws Exception {
        CreditProduct inactive = new CreditProduct();
        inactive.setId("retired-scheme");
        inactive.setActive(false);
        when(products.findById("retired-scheme")).thenReturn(Optional.of(inactive));

        mvc.perform(get("/api/v2/credit-partners/nearby")
                        .param("lat", "28.6").param("lng", "77.2").param("schemeId", "retired-scheme"))
                .andExpect(status().isBadRequest());
    }
}
