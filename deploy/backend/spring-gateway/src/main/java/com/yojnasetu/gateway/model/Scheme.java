package com.yojnasetu.gateway.model;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * Per CLAUDE.md's `schemes` collection. Shape matches what
 * ai_service/scripts/migrate_schemes.py and discovery/upsert.py actually
 * write (see ADR-001 context) — Spring Data MongoDB ignores document fields
 * with no matching property (embedding, contentHash, needsEmbedding,
 * discoverySource), so this class only maps what the gateway needs to read;
 * it is not the source of truth for scheme data, ai_service is.
 */
@Document(collection = "schemes")
@Data
@NoArgsConstructor
public class Scheme {

    @Id
    private String id;

    // Names below match ai_service's already-created indexes on this shared collection —
    // ai_service is the source of truth for schemes; auto-index-creation would otherwise
    // fail at boot with IndexOptionsConflict: same keys, different name.
    @Indexed(name = "schemeCode_1", unique = true)
    private String schemeCode;

    private String name;
    private String ministry;

    @Indexed(name = "state_1")
    private String state; // null = central scheme

    private List<String> category;
    private String sector;
    private Map<String, Object> eligibilityRules;
    private String eligibilityText;
    private String benefitAmount;
    private List<String> documents;
    private String applyUrl;
    private LocalDateTime lastUpdated;
}
