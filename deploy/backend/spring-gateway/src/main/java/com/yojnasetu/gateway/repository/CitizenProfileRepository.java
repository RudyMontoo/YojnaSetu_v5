package com.yojnasetu.gateway.repository;

import com.yojnasetu.gateway.model.CitizenProfile;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.Optional;

public interface CitizenProfileRepository extends MongoRepository<CitizenProfile, String> {
    Optional<CitizenProfile> findByUserId(String userId);
}
