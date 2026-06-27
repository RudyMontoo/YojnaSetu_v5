package com.yojnasetu.gateway.model;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

import java.time.LocalDateTime;

/**
 * Per CLAUDE.md's `trend_events` collection (TTL 30 days). Field names are
 * snake_case in Mongo (CLAUDE.md's schema) — ai_service writes them that
 * way — hence the @Field mappings.
 *
 * Deliberately NO index annotations here: ai_service's ensure_indexes()
 * owns this collection's indexes (TTL on `at`, compound on
 * scheme_code/user_state/at). Declaring them here too would recreate the
 * IndexOptionsConflict boot failure we hit on schemes/citizen_profiles —
 * same keys, different auto-generated names, app refuses to start.
 */
@Document(collection = "trend_events")
@Data
@NoArgsConstructor
public class TrendEvent {

    @Id
    private String id;

    @Field("scheme_code")
    private String schemeCode;

    @Field("scheme_name")
    private String schemeName;

    /** search | save | view */
    @Field("event_type")
    private String eventType;

    @Field("user_state")
    private String userState;

    @Field("at")
    private LocalDateTime at;

    public static TrendEvent of(String schemeCode, String schemeName, String eventType, String userState) {
        TrendEvent e = new TrendEvent();
        e.setSchemeCode(schemeCode);
        e.setSchemeName(schemeName);
        e.setEventType(eventType);
        e.setUserState(userState);
        e.setAt(LocalDateTime.now());
        return e;
    }
}
