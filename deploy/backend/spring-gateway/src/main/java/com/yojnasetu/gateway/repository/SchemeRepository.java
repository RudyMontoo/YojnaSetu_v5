package com.yojnasetu.gateway.repository;

import com.yojnasetu.gateway.model.Scheme;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.Optional;

public interface SchemeRepository extends MongoRepository<Scheme, String> {
    Optional<Scheme> findBySchemeCode(String schemeCode);
}
