package com.yojnasetu.gateway.repository;

import com.yojnasetu.gateway.model.AgentAlert;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.data.mongodb.repository.Query;

import java.util.List;

public interface AgentAlertRepository extends MongoRepository<AgentAlert, String> {

    /**
     * Alerts that still need attention AND haven't been emailed yet. `$ne: true`
     * (rather than `false`) so it also catches docs where the field is missing or
     * null — Python writers set resolved=false and never set `notified` at all.
     */
    @Query("{ 'resolved': { $ne: true }, 'notified': { $ne: true } }")
    List<AgentAlert> findUnresolvedUnnotified();
}
