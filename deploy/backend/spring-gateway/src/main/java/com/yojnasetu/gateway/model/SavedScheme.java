package com.yojnasetu.gateway.model;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.CompoundIndex;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * A pure bookmark — "I'm interested in this scheme," nothing more. Deliberately
 * separate from Application (the `applications` collection): saving/unsaving
 * here never creates, touches, or implies any application lifecycle status.
 * See Application.java for the actual tracked-application model.
 */
@Document(collection = "saved_schemes")
@CompoundIndex(name = "user_scheme_unique", def = "{'userId': 1, 'schemeCode': 1}", unique = true)
@Data
@NoArgsConstructor
public class SavedScheme {

    @Id
    private String id;

    private String userId;
    private String schemeId;

    // Denormalized — avoids an extra lookup on the list view
    private String schemeCode;
    private String schemeName;

    private LocalDateTime savedAt;
}
