package com.yojnasetu.gateway.repository;

import com.yojnasetu.gateway.model.SavedScheme;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;
import java.util.Optional;

public interface SavedSchemeRepository extends MongoRepository<SavedScheme, String> {
    List<SavedScheme> findByUserId(String userId);
    Optional<SavedScheme> findByUserIdAndSchemeCode(String userId, String schemeCode);
    void deleteByUserIdAndSchemeCode(String userId, String schemeCode);
}
