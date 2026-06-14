package com.yojnasetu.gateway.repository;

import com.yojnasetu.gateway.model.AuditLog;
import org.springframework.data.mongodb.repository.MongoRepository;

public interface AuditLogRepository extends MongoRepository<AuditLog, String> {
}
