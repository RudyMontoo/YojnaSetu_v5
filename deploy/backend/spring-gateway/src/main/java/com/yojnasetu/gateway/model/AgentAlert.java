package com.yojnasetu.gateway.model;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

import java.time.Instant;

/**
 * Read model over the `agent_alerts` collection that the Python ai_service
 * writes (agent failures, zero-candidate discovery runs, etc.). Field names are
 * snake_case because that's what Python writes — mapped explicitly with @Field.
 *
 * Deliberately declares NO indexes: per CLAUDE.md, ai_service's ensure_indexes()
 * owns index creation on shared collections (agent_alerts has a TTL index there);
 * a second service declaring the same index under a different name = boot failure.
 *
 * `notified` is the one field the gateway owns — set true once AlertNotifier has
 * emailed the admin about this alert, so it isn't re-sent every poll. Python
 * writers don't set it (absent == not yet notified).
 */
@Document(collection = "agent_alerts")
@Data
@NoArgsConstructor
public class AgentAlert {

    @Id
    private String id;

    @Field("agent_name")
    private String agentName;

    @Field("alert_type")
    private String alertType;

    private String message;

    private Instant at;

    private Boolean resolved;

    /** Gateway-owned: has the admin already been emailed about this alert? */
    private Boolean notified;
}
