package com.yojnasetu.gateway.repository;

import com.yojnasetu.gateway.model.OtpSession;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.Optional;

public interface OtpSessionRepository extends MongoRepository<OtpSession, String> {
    Optional<OtpSession> findByPhone(String phone);
    void deleteByPhone(String phone);
}
