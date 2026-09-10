package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.model.AgentAlert;
import com.yojnasetu.gateway.repository.AgentAlertRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class MisuseReportServiceTest {

    private MisuseReportRepository reports;
    private BranchRepRepository helpers;
    private AgentAlertRepository alerts;
    private MisuseReportService service;

    @BeforeEach
    void setUp() {
        reports = mock(MisuseReportRepository.class);
        helpers = mock(BranchRepRepository.class);
        alerts = mock(AgentAlertRepository.class);

        when(reports.save(any(MisuseReport.class))).thenAnswer(i -> {
            MisuseReport r = i.getArgument(0);
            if (r.getId() == null) {
                r.setId("report-1");
            }
            return r;
        });
        when(helpers.findById(anyString())).thenReturn(Optional.empty());
        when(helpers.findByRepId(anyString())).thenReturn(Optional.empty());

        service = new MisuseReportService(reports, helpers, alerts);
    }

    @Test
    void filesAReportAndPutsItInFrontOfAHuman() {
        // A report that lands in a collection nobody watches is worse than no
        // channel at all — it tells the applicant they were heard when they
        // were not.
        service.file("citizen-1", "app-1", null,
                MisuseReport.Category.UNOFFICIAL_FEE, "He asked for 500 rupees.");

        verify(alerts).save(any(AgentAlert.class));
    }

    @Test
    void theAlertCarriesIdsNotTheApplicantsWords() {
        service.file("citizen-1", "app-1", null,
                MisuseReport.Category.UNOFFICIAL_FEE, "He asked for 500 rupees at the centre in Ranchi.");

        ArgumentCaptor<AgentAlert> captor = ArgumentCaptor.forClass(AgentAlert.class);
        verify(alerts).save(captor.capture());
        String message = captor.getValue().getMessage();

        assertTrue(message.contains("report-1"), "the alert must point at the report");
        assertTrue(message.contains("app-1"));
        // agent_alerts is TTL'd, emailed in a digest, and this codebase's rule
        // is that PII stays out of logs. The applicant's account of what
        // happened routinely names people and places.
        assertTrue(!message.contains("Ranchi") && !message.contains("500 rupees"),
                () -> "the applicant's description leaked into an operational alert: " + message);
    }

    @Test
    void acceptsAReportEvenWhenTheHelperCannotBeIdentified() {
        // "Someone at the centre asked me for money" is worth having even when
        // the applicant never learned who it was.
        MisuseReport filed = service.file("citizen-1", "app-1", "WHOEVER-IT-WAS",
                MisuseReport.Category.UNOFFICIAL_FEE, "Someone at the counter asked for money.");

        assertEquals(MisuseReport.Status.OPEN, filed.getStatus());
        assertNotNull(filed.getCreatedAt());
    }

    @Test
    void resolvesAHelperNamedByTheirCardIdToTheirAccount() {
        BranchRep helper = new BranchRep();
        helper.setId("h-1");
        helper.setRepId("CSC-JH-201");
        helper.setName("R. Devi");
        helper.setRepType(RepType.CSC);
        when(helpers.findByRepId("CSC-JH-201")).thenReturn(Optional.of(helper));

        MisuseReport filed = service.file("citizen-1", "app-1", "CSC-JH-201",
                MisuseReport.Category.CREDENTIAL_REQUEST, "Asked me for the OTP on my phone.");

        assertEquals("h-1", filed.getReportedHelperId());
        assertEquals("R. Devi", filed.getReportedHelperName());
    }

    @Test
    void refusesAnEmptyDescriptionBecauseThereWouldBeNothingToActOn() {
        var e = assertThrows(CreditApplicationService.TransitionException.class,
                () -> service.file("citizen-1", "app-1", null, MisuseReport.Category.OTHER, "   "));
        assertEquals(CreditApplicationService.Failure.BAD_REQUEST, e.failure());
    }

    @Test
    void refusesAReportWithNoCategory() {
        var e = assertThrows(CreditApplicationService.TransitionException.class,
                () -> service.file("citizen-1", "app-1", null, null, "Something happened."));
        assertEquals(CreditApplicationService.Failure.BAD_REQUEST, e.failure());
    }

    @Test
    void aFailedAlertDoesNotLoseTheReport() {
        when(alerts.save(any(AgentAlert.class))).thenThrow(new RuntimeException("mongo down"));

        MisuseReport filed = service.file("citizen-1", "app-1", null,
                MisuseReport.Category.DATA_MISUSE, "My documents were used elsewhere.");

        assertNotNull(filed.getId(), "the report is saved before the alert is attempted");
    }

    @Test
    void resolvingRecordsWhatWasDoneSoTheApplicantCanBeTold() {
        MisuseReport existing = new MisuseReport();
        existing.setId("report-1");
        existing.setStatus(MisuseReport.Status.OPEN);
        when(reports.findById("report-1")).thenReturn(Optional.of(existing));

        MisuseReport resolved = service.resolve("report-1", MisuseReport.Status.RESOLVED,
                "Helper account deactivated pending review.");

        assertEquals(MisuseReport.Status.RESOLVED, resolved.getStatus());
        assertNotNull(resolved.getResolvedAt());
        assertEquals("Helper account deactivated pending review.", resolved.getResolutionNote());
    }

    @Test
    void resolvingSomethingThatIsNotThereIsA404NotASilentNoop() {
        when(reports.findById("nope")).thenReturn(Optional.empty());

        var e = assertThrows(CreditApplicationService.TransitionException.class,
                () -> service.resolve("nope", MisuseReport.Status.RESOLVED, "x"));

        assertEquals(CreditApplicationService.Failure.NOT_FOUND, e.failure());
    }
}
