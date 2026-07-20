package com.yojnasetu.gateway.controller;

import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * GET /api/v2/schemes — the browsable scheme catalogue.
 *
 * Built 2026-07-07 because the frontend SchemesPage was still rendering a
 * hardcoded 8-scheme demo list while Mongo held 1,900+ real schemes — this
 * is the first endpoint that pages through the full collection. Any JWT
 * (same trust level as /schemes/trending; catalogue browsing is
 * citizen-facing, not admin).
 *
 * Filters:
 *   ?search=  case-insensitive contains on name OR ministry (user input is
 *             Pattern.quote()d — never interpreted as regex)
 *   ?sector=  comma-separated, case-insensitive contains on the sector
 *             field, OR'd (e.g. "business,banking,entrepreneur"). Sector
 *             values come from MyScheme's own taxonomy and the original
 *             seed data ("Agriculture,Rural & Environment", "housing", …) —
 *             contains-matching bridges the two spellings.
 *   ?page/?size  skip/limit pagination, size capped at 50. Sorted by name
 *             so the catalogue reads like a directory, not by insert order.
 */
@RestController
@RequestMapping("/api/v2")
public class SchemeCatalogueController {

    private static final int MAX_PAGE_SIZE = 50;
    private static final int DEFAULT_PAGE_SIZE = 24;

    private final MongoTemplate mongoTemplate;

    public SchemeCatalogueController(MongoTemplate mongoTemplate) {
        this.mongoTemplate = mongoTemplate;
    }

    @GetMapping("/schemes")
    public ResponseEntity<?> listSchemes(
            @RequestParam(required = false) String search,
            @RequestParam(required = false) String sector,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "" + DEFAULT_PAGE_SIZE) int size) {

        int safeSize = Math.max(1, Math.min(size, MAX_PAGE_SIZE));
        int safePage = Math.max(0, page);

        List<Criteria> ands = new ArrayList<>();

        if (search != null && !search.isBlank()) {
            String quoted = Pattern.quote(search.trim());
            ands.add(new Criteria().orOperator(
                    Criteria.where("name").regex(quoted, "i"),
                    Criteria.where("ministry").regex(quoted, "i")));
        }

        if (sector != null && !sector.isBlank()) {
            List<Criteria> sectorOrs = new ArrayList<>();
            for (String part : sector.split(",")) {
                if (!part.isBlank()) {
                    sectorOrs.add(Criteria.where("sector").regex(Pattern.quote(part.trim()), "i"));
                }
            }
            if (!sectorOrs.isEmpty()) {
                ands.add(new Criteria().orOperator(sectorOrs.toArray(new Criteria[0])));
            }
        }

        Criteria criteria = ands.isEmpty()
                ? new Criteria()
                : new Criteria().andOperator(ands.toArray(new Criteria[0]));

        Query countQuery = new Query(criteria);
        long total = mongoTemplate.count(countQuery, "schemes");

        // Rank: trending / most-applied FIRST (popularityScore, written by
        // ai_service/scripts/recompute_popularity.py from real trend_events +
        // applications), then newest (lastUpdated), then name as a stable
        // tie-break. Applies WITHIN whatever category/search filter is active,
        // so every sector surfaces its hottest + freshest schemes at the top
        // instead of an alphabetical directory. Schemes with no activity have
        // popularityScore 0 and simply fall back to newest-first.
        Query query = new Query(criteria)
                .with(Sort.by(Sort.Direction.DESC, "popularityScore")
                        .and(Sort.by(Sort.Direction.DESC, "lastUpdated"))
                        .and(Sort.by(Sort.Direction.ASC, "name")))
                .skip((long) safePage * safeSize)
                .limit(safeSize);
        query.fields().include("schemeCode", "name", "benefitAmount", "sector",
                "state", "ministry", "applyUrl");

        List<Map> schemes = mongoTemplate.find(query, Map.class, "schemes");
        schemes.forEach(s -> s.remove("_id")); // ObjectId isn't JSON-serializable and isn't the public identifier

        return ResponseEntity.ok(Map.of(
                "schemes", schemes,
                "total", total,
                "page", safePage,
                "size", safeSize,
                "has_more", (long) (safePage + 1) * safeSize < total));
    }
}
