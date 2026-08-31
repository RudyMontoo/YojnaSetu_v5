package com.yojnasetu.gateway.model;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.CompoundIndex;
import org.springframework.data.mongodb.core.index.CompoundIndexes;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * Tracks the real lifecycle of an application a citizen has actually started —
 * NOT a bookmark (see SavedScheme.java for that). A row here is only created
 * once a citizen has taken a genuine "I'm applying" action (clicking through
 * to the official portal, or explicitly marking a scheme as started); the
 * former "saved" pseudo-status that conflated bookmarking with tracking has
 * been removed.
 */
@Document(collection = "applications")
@CompoundIndexes({
        @CompoundIndex(name = "user_status", def = "{'userId': 1, 'status': 1}"),
        @CompoundIndex(name = "user_scheme_unique", def = "{'userId': 1, 'schemeId': 1}", unique = true)
})
@Data
@NoArgsConstructor
public class Application {

    @Id
    private String id;

    private String userId;
    private String schemeId;

    // Denormalized — avoids an extra lookup on the list view
    private String schemeCode;
    private String schemeName;

    /** in_progress | submitted | approved | rejected | disbursed */
    private String status = "in_progress";

    private List<StatusEntry> statusHistory = new ArrayList<>();

    private String externalAppId;
    private Integer eligibilityScore;

    private LocalDateTime appliedAt;
    private LocalDateTime lastStatusCheck;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class StatusEntry {
        private String status;
        private LocalDateTime at;
    }
}
