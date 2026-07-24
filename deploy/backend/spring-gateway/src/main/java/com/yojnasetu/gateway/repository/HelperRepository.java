package com.yojnasetu.gateway.repository;

import com.yojnasetu.gateway.model.Helper;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;
import java.util.Optional;

public interface HelperRepository extends MongoRepository<Helper, String> {
    Optional<Helper> findByHelperId(String helperId);
    List<Helper> findByOrderByCreatedAtDesc();
}
