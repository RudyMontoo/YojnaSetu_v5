package com.yojnasetu.gateway.credit;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.ArgumentCaptor;

import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ChannelPartnerTypeTest {

    private final ObjectMapper mapper = new ObjectMapper();

    @Test
    void serialisesToTheStringsTheLocatorAlreadyReturns() throws Exception {
        // "PSB"/"RRB"/"Unclassified" were already on the wire before channel
        // types existed — changing them would silently break the locator UI.
        assertEquals("\"PSB\"", mapper.writeValueAsString(ChannelPartnerType.PSB));
        assertEquals("\"RRB\"", mapper.writeValueAsString(ChannelPartnerType.RRB));
        assertEquals("\"Unclassified\"", mapper.writeValueAsString(ChannelPartnerType.UNCLASSIFIED));
        assertEquals("\"NBFC-MFI\"", mapper.writeValueAsString(ChannelPartnerType.NBFC_MFI));
    }

    @ParameterizedTest
    @ValueSource(strings = {"NBFC-MFI", "nbfc_mfi", "NBFC_MFI", "nbfc-mfi"})
    void acceptsEitherSpellingOnInput(String wire) {
        assertEquals(ChannelPartnerType.NBFC_MFI, ChannelPartnerType.fromWire(wire));
    }

    @Test
    void rejectsAnUnknownType() {
        assertThrows(IllegalArgumentException.class, () -> ChannelPartnerType.fromWire("chit-fund"));
    }

    @Test
    void knowsWhichChannelsABankSearchCanActuallyFind() {
        // A State Channelising Agency is a government corporation, not a
        // tagged bank branch. Claiming the locator covers them would make an
        // empty result read as "no help near you".
        assertFalse(ChannelPartnerType.SCA.appearsInOpenStreetMap());
        assertFalse(ChannelPartnerType.NBFC_MFI.appearsInOpenStreetMap());
        assertTrue(ChannelPartnerType.PSB.appearsInOpenStreetMap());
        assertTrue(ChannelPartnerType.RRB.appearsInOpenStreetMap());
    }

    @ParameterizedTest
    @EnumSource(ChannelPartnerType.class)
    void everyTypeIsRoundTrippable(ChannelPartnerType type) {
        assertEquals(type, ChannelPartnerType.fromWire(type.wireName()));
        assertNotNull(type.label());
    }

    // ---- the seeded channel mappings ----

    @Test
    void everySeededSchemeDeclaresHowItIsDelivered() {
        seeded().forEach((id, product) -> {
            assertNotNull(product.getChannelPartnerTypes(), () -> id + " has no channel list");
            assertFalse(product.getChannelPartnerTypes().isEmpty(), () -> id + " has an empty channel list");
        });
    }

    @Test
    void routesTheExpensiveMicroFinanceThroughTheMfiChannelOnly() {
        // This is the pair that makes the whole feature matter: identical
        // money, 6.5% via an SCA and 15% via an NBFC-MFI.
        Map<String, CreditProduct> products = seeded();

        assertEquals(List.of(ChannelPartnerType.NBFC_MFI),
                products.get("aajeevika-micro-finance").getChannelPartnerTypes());
        assertTrue(products.get("micro-finance").getChannelPartnerTypes()
                .contains(ChannelPartnerType.SCA));
        assertFalse(products.get("micro-finance").getChannelPartnerTypes()
                .contains(ChannelPartnerType.NBFC_MFI));

        assertTrue(products.get("aajeevika-micro-finance").getInterestRate()
                > products.get("micro-finance").getInterestRate());
    }

    @Test
    void keepsTheWomensSchemeOnItsConcessionalChannels() {
        List<ChannelPartnerType> channels =
                seeded().get("mahila-samriddhi").getChannelPartnerTypes();

        assertTrue(channels.contains(ChannelPartnerType.SCA));
        // Routing a 4% scheme through the 15% channel would defeat its purpose.
        assertFalse(channels.contains(ChannelPartnerType.NBFC_MFI));
    }

    @Test
    void everySchemeHasAtLeastOneChannelACitizenCanBeSentTo() {
        // Either something a bank search can find, or an off-map channel the
        // response explicitly names. A scheme with neither would be a dead end.
        seeded().forEach((id, product) -> assertTrue(
                product.getChannelPartnerTypes().stream().anyMatch(ChannelPartnerType::appearsInOpenStreetMap)
                        || product.getChannelPartnerTypes().stream().anyMatch(t -> !t.appearsInOpenStreetMap()),
                () -> id + " cannot be reached through any channel"));
    }

    private static Map<String, CreditProduct> seeded() {
        CreditProductRepository repo = mock(CreditProductRepository.class);
        when(repo.existsById(anyString())).thenReturn(false);
        new CreditProductSeeder(repo).run();
        ArgumentCaptor<CreditProduct> captor = ArgumentCaptor.forClass(CreditProduct.class);
        verify(repo, atLeastOnce()).save(captor.capture());
        return captor.getAllValues().stream()
                .collect(Collectors.toMap(CreditProduct::getId, Function.identity()));
    }
}
