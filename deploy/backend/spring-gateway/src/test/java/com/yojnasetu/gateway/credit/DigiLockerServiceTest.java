package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import com.yojnasetu.gateway.security.FieldEncryptionService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.ExchangeFunction;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.Base64;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * DigiLockerService against a fake ExchangeFunction — no real DigiLocker
 * sandbox exists to test this against (see the class javadoc), so this pins
 * the request/response SHAPE the code builds and parses rather than proving
 * it works against DigiLocker's real servers.
 */
class DigiLockerServiceTest {

    private static final FieldEncryptionService CIPHER = new FieldEncryptionService(
            Base64.getEncoder().encodeToString(new byte[32]));

    private DigiLockerLinkRepository links;
    private ConsentService consents;

    @BeforeEach
    void setUp() {
        links = mock(DigiLockerLinkRepository.class);
        consents = mock(ConsentService.class);
        when(links.save(any(DigiLockerLink.class))).thenAnswer(inv -> inv.getArgument(0));
    }

    private DigiLockerService serviceWithFakeResponse(String json, int status) {
        ExchangeFunction fake = request -> Mono.just(
                ClientResponse.create(HttpStatus.valueOf(status))
                        .header("Content-Type", "application/json")
                        .body(json)
                        .build());
        WebClient client = WebClient.builder().exchangeFunction(fake).build();
        return new DigiLockerService(links, consents, CIPHER,
                "client-1", "secret-1", "https://app.example/callback",
                "https://digilocker.example", client);
    }

    private DigiLockerService unconfiguredService() {
        return new DigiLockerService(links, consents, CIPHER, "", "", "",
                "https://digilocker.example", WebClient.builder().build());
    }

    // ---------------------------------------------------------- isConfigured

    @Test
    void refusesEveryEntryPointWhenNoCredentialsAreConfigured() {
        DigiLockerService service = unconfiguredService();
        assertFalse(service.isConfigured());

        assertEquals(Failure.BAD_REQUEST,
                assertThrows(TransitionException.class, () -> service.startLink("u-1", "app-1")).failure());
        assertEquals(Failure.BAD_REQUEST,
                assertThrows(TransitionException.class, () -> service.completeLink("s", "c")).failure());
    }

    // -------------------------------------------------------------- startLink

    @Test
    void startLinkRequiresConsentFirst() {
        DigiLockerService service = serviceWithFakeResponse("{}", 200);
        org.mockito.Mockito.doThrow(new TransitionException(Failure.FORBIDDEN, "consent needed"))
                .when(consents).requireConsent("u-1", ConsentPurpose.DIGILOCKER_FETCH, "app-1");

        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.startLink("u-1", "app-1"));
        assertEquals(Failure.FORBIDDEN, thrown.failure());
    }

    @Test
    void startLinkBuildsAnAuthorizeUrlAndRecordsAPendingState() {
        DigiLockerService service = serviceWithFakeResponse("{}", 200);

        DigiLockerService.AuthorizeUrl result = service.startLink("u-1", "app-1");

        assertTrue(result.url().startsWith("https://digilocker.example/public/oauth2/1/authorize"));
        assertTrue(result.url().contains("client_id=client-1"));
        assertTrue(result.url().contains("state=" + result.state()));
        verify(links).save(any(DigiLockerLink.class));
    }

    // ------------------------------------------------------------ completeLink

    @Test
    void completeLinkRefusesAnUnknownState() {
        DigiLockerService service = serviceWithFakeResponse("{}", 200);
        when(links.findByState("ghost")).thenReturn(Optional.empty());

        assertEquals(Failure.NOT_FOUND,
                assertThrows(TransitionException.class, () -> service.completeLink("ghost", "code")).failure());
    }

    @Test
    void completeLinkRefusesAStateThatWasAlreadyConsumed() {
        DigiLockerLink already = new DigiLockerLink();
        already.setState("used");
        already.setStatus("linked");
        when(links.findByState("used")).thenReturn(Optional.of(already));

        DigiLockerService service = serviceWithFakeResponse("{}", 200);
        assertEquals(Failure.CONFLICT,
                assertThrows(TransitionException.class, () -> service.completeLink("used", "code")).failure());
    }

    @Test
    void completeLinkExchangesTheCodeAndEncryptsTheAccessToken() {
        DigiLockerLink pending = new DigiLockerLink();
        pending.setState("s-1");
        pending.setStatus("pending");
        when(links.findByState("s-1")).thenReturn(Optional.of(pending));

        String tokenResponse = """
                {"access_token":"real-token-xyz","expires_in":3600,"digilockerid":"dl-uid-1"}""";
        DigiLockerService service = serviceWithFakeResponse(tokenResponse, 200);

        DigiLockerLink linked = service.completeLink("s-1", "auth-code");

        assertEquals("linked", linked.getStatus());
        assertEquals("dl-uid-1", linked.getDigilockerUid());
        assertNotEquals("real-token-xyz", linked.getAccessToken(), "access token must not be stored in the clear");
        assertEquals("real-token-xyz", CIPHER.decrypt(linked.getAccessToken()));
    }

    @Test
    void completeLinkRejectsAResponseWithNoAccessToken() {
        DigiLockerLink pending = new DigiLockerLink();
        pending.setState("s-1");
        pending.setStatus("pending");
        when(links.findByState("s-1")).thenReturn(Optional.of(pending));

        DigiLockerService service = serviceWithFakeResponse("{\"error\":\"invalid_grant\"}", 200);

        assertEquals(Failure.BAD_REQUEST,
                assertThrows(TransitionException.class, () -> service.completeLink("s-1", "bad-code")).failure());
    }

    // ---------------------------------------------------------------- fetch

    @Test
    void refusesToFetchDocumentsWithoutALinkedAccount() {
        DigiLockerService service = serviceWithFakeResponse("{}", 200);
        when(links.findFirstByApplicationIdAndStatusOrderByCreatedAtDesc("app-1", "linked"))
                .thenReturn(Optional.empty());

        assertEquals(Failure.CONFLICT,
                assertThrows(TransitionException.class, () -> service.fetchIssuedDocuments("app-1")).failure());
    }

    @Test
    void fetchesAndParsesTheIssuedDocumentsList() {
        DigiLockerLink linked = new DigiLockerLink();
        linked.setApplicationId("app-1");
        linked.setStatus("linked");
        linked.setAccessToken(CIPHER.encrypt("tok"));
        when(links.findFirstByApplicationIdAndStatusOrderByCreatedAtDesc("app-1", "linked"))
                .thenReturn(Optional.of(linked));

        String body = """
                {"items":[{"name":"Income Certificate","type":"certificate","doctype":"INCOME",
                           "uri":"in.gov.example-INCOME-1","mime":"application/pdf","date":"2026-01-01"}]}""";
        DigiLockerService service = serviceWithFakeResponse(body, 200);

        var documents = service.fetchIssuedDocuments("app-1");

        assertEquals(1, documents.size());
        assertEquals("Income Certificate", documents.get(0).name());
        assertEquals("in.gov.example-INCOME-1", documents.get(0).uri());
    }
}
