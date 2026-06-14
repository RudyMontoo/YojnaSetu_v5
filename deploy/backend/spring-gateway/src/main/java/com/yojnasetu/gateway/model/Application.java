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

/** Per CLAUDE.md's `applications` collection. */
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

    /** saved | in_progress | submitted | approved | rejected | disbursed */
    private String status = "saved";

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
