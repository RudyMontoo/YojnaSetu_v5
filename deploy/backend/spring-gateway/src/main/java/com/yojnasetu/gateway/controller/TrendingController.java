package com.yojnasetu.gateway.controller;

import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.aggregation.Aggregation;
import org.springframework.data.mongodb.core.aggregation.AggregationResults;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Per CLAUDE.md's endpoint table:
 *   GET  /api/v2/schemes/trending        — any JWT — top 5 by 7-day trend_events count,
 *                                          cached 6h; optional ?state=UP scopes to events
 *                                          from citizens of that state.
 *   POST /api/v2/admin/trend/recompute   — Admin JWT — drops the cache so the next read
 *                                          recomputes immediately (emergency refresh).
 *
 * The aggregation is CLAUDE.md's own, keyed by scheme_code instead of scheme_id
 * (see TrendEvent's class doc). Cache is in-memory per instance — fine for one
 * gateway node; a multi-instance deployment would move this to a shared store,
 * which is a Phase 11 concern.
 */
@RestController
@RequestMapping("/api/v2")
public class TrendingController {

    private static final long CACHE_TTL_MILLIS = 6 * 60 * 60 * 1000L;
    private static final int TOP_N = 5;
    private static final int WINDOW_DAYS = 7;

    private final MongoTemplate mongoTemplate;
    private final Map<String, CacheEntry> cache = new ConcurrentHashMap<>();

    private record CacheEntry(List<Map<String, Object>> result, long computedAtMillis) {}

    public TrendingController(MongoTemplate mongoTemplate) {
        this.mongoTemplate = mongoTemplate;
    }

    @GetMapping("/schemes/trending")
    public ResponseEntity<?> trending(@RequestParam(required = false) String state) {
        String cacheKey = (state == null || state.isBlank()) ? "__national__" : state.trim().toUpperCase();

        CacheEntry cached = cache.get(cacheKey);
        long now = System.currentTimeMillis();
        if (cached != null && now - cached.computedAtMillis() < CACHE_TTL_MILLIS) {
            return ResponseEntity.ok(Map.of(
                    "trending", cached.result(),
                    "cached", true,
                    "computed_at", Instant.ofEpochMilli(cached.computedAtMillis()).toString()));
        }

        List<Map<String, Object>> result = compute(cacheKey.equals("__national__") ? null : cacheKey);
        cache.put(cacheKey, new CacheEntry(result, now));
        return ResponseEntity.ok(Map.of(
                "trending", result,
                "cached", false,
                "computed_at", Instant.ofEpochMilli(now).toString()));
    }

    @PostMapping("/admin/trend/recompute")
    public ResponseEntity<?> recompute(Authentication auth) {
        boolean isAdmin = auth != null && auth.getAuthorities().stream()
                .map(GrantedAuthority::getAuthority)
                .anyMatch("ROLE_ADMIN"::equals);
        if (!isAdmin) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Admin role required"));
        }
        cache.clear();
        return ResponseEntity.ok(Map.of("success", true, "message", "Trending cache cleared — next read recomputes"));
    }

    private List<Map<String, Object>> compute(String state) {
        Criteria criteria = Criteria.where("at").gte(LocalDateTime.now().minusDays(WINDOW_DAYS));
        if (state != null) {
            criteria = criteria.and("user_state").is(state);
        }

        Aggregation agg = Aggregation.newAggregation(
                Aggregation.match(criteria),
                Aggregation.group("scheme_code")
                        .count().as("count")
                        .first("scheme_name").as("scheme_name"),
                Aggregation.sort(Sort.Direction.DESC, "count"),
                Aggregation.limit(TOP_N));

        AggregationResults<org.bson.Document> results =
                mongoTemplate.aggregate(agg, "trend_events", org.bson.Document.class);
        return results.getMappedResults().stream()
                .map(d -> Map.<String, Object>of(
                        "scheme_code", String.valueOf(d.get("_id")),
                        "scheme_name", d.get("scheme_name") != null ? d.get("scheme_name") : "",
                        "count", d.get("count")))
                .toList();
    }
}
