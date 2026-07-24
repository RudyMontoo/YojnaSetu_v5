package com.yojnasetu.gateway.repository;

import com.yojnasetu.gateway.model.Kendra;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface KendraRepository extends MongoRepository<Kendra, String> {
    List<Kendra> findByActiveTrue();
    List<Kendra> findByHelperId(String helperId);
}
