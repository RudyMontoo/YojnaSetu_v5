package com.yojnasetu.gateway.controller;

import com.yojnasetu.gateway.model.SavedScheme;
import com.yojnasetu.gateway.model.Scheme;
import com.yojnasetu.gateway.repository.SavedSchemeRepository;
import com.yojnasetu.gateway.repository.SchemeRepository;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * Pure bookmarking — "I'm interested in this scheme," nothing more. Deliberately
 * separate from ApplicationController: saving/unsaving here never creates or
 * mutates a tracked application. A citizen can freely save/unsave a scheme
 * regardless of whether they also have (or don't have) an application being
 * tracked for the same scheme.
 */
@RestController
@RequestMapping("/api/v2/saved-schemes")
public class SavedSchemeController {

    private final SavedSchemeRepository repo;
    private final SchemeRepository schemeRepository;

    public SavedSchemeController(SavedSchemeRepository repo, SchemeRepository schemeRepository) {
        this.repo = repo;
        this.schemeRepository = schemeRepository;
    }

    @GetMapping
    public ResponseEntity<?> list(Authentication auth) {
        return ResponseEntity.ok(repo.findByUserId(auth.getName()));
    }

    public record SaveRequest(String schemeCode) {}

    /** Idempotent: saving an already-saved scheme just returns the existing bookmark (200), not a conflict. */
    @PostMapping
    public ResponseEntity<?> save(Authentication auth, @RequestBody SaveRequest req) {
        String userId = auth.getName();
        if (req.schemeCode() == null || req.schemeCode().isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "schemeCode is required"));
        }

        var existing = repo.findByUserIdAndSchemeCode(userId, req.schemeCode());
        if (existing.isPresent()) {
            return ResponseEntity.ok(existing.get());
        }

        Scheme scheme = schemeRepository.findBySchemeCode(req.schemeCode()).orElse(null);
        if (scheme == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Unknown schemeCode: " + req.schemeCode()));
        }

        SavedScheme s = new SavedScheme();
        s.setUserId(userId);
        s.setSchemeId(scheme.getId());
        s.setSchemeCode(scheme.getSchemeCode());
        s.setSchemeName(scheme.getName());
        s.setSavedAt(LocalDateTime.now());
        return ResponseEntity.status(HttpStatus.CREATED).body(repo.save(s));
    }

    /** Idempotent: unsaving a scheme that isn't saved is still a success — the end state is what the citizen wanted. */
    @DeleteMapping("/{schemeCode}")
    public ResponseEntity<?> unsave(Authentication auth, @PathVariable String schemeCode) {
        repo.deleteByUserIdAndSchemeCode(auth.getName(), schemeCode);
        return ResponseEntity.ok(Map.of("success", true));
    }
}
