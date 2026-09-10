package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.ExchangeFunction;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class AccountAggregatorServiceTest {

    private AaConsentRequestRepository consentRequests;
    private ConsentService consents;

    @BeforeEach
    void setUp() {
        consentRequests = mock(AaConsentRequestRepository.class);
        consents = mock(ConsentService.class);
        when(consentRequests.save(any(AaConsentRequest.class))).thenAnswer(inv -> inv.getArgument(0));
    }

    private AccountAggregatorService serviceWithFakeResponse(String json, int status) {
        ExchangeFunction fake = request -> Mono.just(
                ClientResponse.create(HttpStatus.valueOf(status))
                        .header("Content-Type", "application/json")
                        .body(json)
                        .build());
        WebClient client = WebClient.builder().exchangeFunction(fake).build();
        return new AccountAggregatorService(consentRequests, consents, "api-key-1", "https://aa.example", client);
    }

    private AccountAggregatorService unconfiguredService() {
        return new AccountAggregatorService(consentRequests, consents, "", "",
                WebClient.builder().build());
    }

    @Test
    void refusesEveryEntryPointWhenNoApiKeyIsConfigured() {
        AccountAggregatorService service = unconfiguredService();
        assertFalse(service.isConfigured());

        assertEquals(Failure.BAD_REQUEST, assertThrows(TransitionException.class,
                () -> service.createConsentRequest("u-1", "app-1", "9999999999@onemoney")).failure());
        assertEquals(Failure.BAD_REQUEST, assertThrows(TransitionException.class,
                () -> service.refreshStatus("handle-1")).failure());
    }

    @Test
    void refusesAConsentRequestWithNoVua() {
        AccountAggregatorService service = serviceWithFakeResponse("{}", 200);
        assertEquals(Failure.BAD_REQUEST, assertThrows(TransitionException.class,
                () -> service.createConsentRequest("u-1", "app-1", " ")).failure());
    }

    @Test
    void createConsentRequestRequiresConsentFirst() {
        AccountAggregatorService service = serviceWithFakeResponse("{}", 200);
        org.mockito.Mockito.doThrow(new TransitionException(Failure.FORBIDDEN, "consent needed"))
                .when(consents).requireConsent("u-1", ConsentPurpose.ACCOUNT_AGGREGATOR_FETCH, "app-1");

        assertEquals(Failure.FORBIDDEN, assertThrows(TransitionException.class,
                () -> service.createConsentRequest("u-1", "app-1", "9999999999@onemoney")).failure());
    }

    @Test
    void createConsentRequestStoresTheHandleFromTheTsp() {
        AccountAggregatorService service = serviceWithFakeResponse(
                "{\"id\":\"consent-handle-abc\",\"status\":\"PENDING\"}", 200);

        AaConsentRequest request = service.createConsentRequest("u-1", "app-1", "9999999999@onemoney");

        assertEquals("consent-handle-abc", request.getConsentHandle());
        assertEquals("pending", request.getStatus());
        assertEquals("9999999999@onemoney", request.getVua());
    }

    @Test
    void createConsentRequestRejectsAResponseWithNoHandle() {
        AccountAggregatorService service = serviceWithFakeResponse("{\"error\":\"bad vua\"}", 200);
        assertEquals(Failure.BAD_REQUEST, assertThrows(TransitionException.class,
                () -> service.createConsentRequest("u-1", "app-1", "9999999999@onemoney")).failure());
    }

    @Test
    void refreshStatusUpdatesTheStoredRecord() {
        AaConsentRequest existing = new AaConsentRequest();
        existing.setConsentHandle("handle-1");
        existing.setStatus("pending");
        when(consentRequests.findByConsentHandle("handle-1")).thenReturn(Optional.of(existing));

        AccountAggregatorService service = serviceWithFakeResponse(
                "{\"status\":\"APPROVED\",\"consentId\":\"consent-real-1\"}", 200);

        AaConsentRequest refreshed = service.refreshStatus("handle-1");

        assertEquals("approved", refreshed.getStatus());
        assertEquals("consent-real-1", refreshed.getConsentId());
    }

    @Test
    void refreshStatusRefusesAnUnknownHandle() {
        when(consentRequests.findByConsentHandle("ghost")).thenReturn(Optional.empty());
        AccountAggregatorService service = serviceWithFakeResponse("{}", 200);

        assertEquals(Failure.NOT_FOUND,
                assertThrows(TransitionException.class, () -> service.refreshStatus("ghost")).failure());
    }

    @Test
    void fetchFinancialDataIsDeliberatelyNotImplemented() {
        AccountAggregatorService service = serviceWithFakeResponse("{}", 200);
        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.fetchFinancialData("handle-1"));
        assertEquals(Failure.BAD_REQUEST, thrown.failure());
        assertEquals(true, thrown.getMessage().contains("not implemented"));
    }
}
