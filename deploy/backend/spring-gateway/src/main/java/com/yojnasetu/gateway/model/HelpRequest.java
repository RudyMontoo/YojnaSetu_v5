package com.yojnasetu.gateway.model;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * A citizen's request for offline/human help — the bridge between "I can't do
 * this myself" and a CSC operator who calls them back. Simple async queue: the
 * citizen files a request, an operator claims it from the dashboard and phones
 * them. No real-time infra needed (per the chosen interaction model).
 */
@Document(collection = "help_requests")
@Data
@NoArgsConstructor
public class HelpRequest {

    @Id
    private String id;

    /** userId of the citizen who asked for help. */
    @Indexed
    private String citizenId;

    /** Display name the citizen typed (optional). */
    private String citizenName;

    /** Callback number the operator should ring. */
    private String phone;

    /** Optional scheme context. */
    private String schemeCode;
    private String schemeName;

    /** What they need help with, in their words. */
    private String message;

    /** waiting | assigned | resolved */
    @Indexed
    private String status = "waiting";

    /** userId of the operator who claimed it (null until claimed). */
    private String assignedOperatorId;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
