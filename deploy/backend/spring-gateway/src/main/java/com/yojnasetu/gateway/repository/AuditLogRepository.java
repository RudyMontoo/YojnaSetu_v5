package com.yojnasetu.gateway.repository;

import com.yojnasetu.gateway.model.AuditLog;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface AuditLogRepository extends MongoRepository<AuditLog, String> {

    /**
     * Every recorded action against one application, newest first — the raw
     * material for the citizen's "who opened my file" view.
     */
    List<AuditLog> findByApplicationIdOrderByAtDesc(String applicationId);
}
