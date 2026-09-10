package com.yojnasetu.gateway.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yojnasetu.gateway.credit.PincodeGeocoder;
import com.yojnasetu.gateway.service.GeoLabelService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Real-bank-branch lookup for the NSFDC Credit & Education Loans module
 * (Geo-Spatial Partner Locator). Proxies OpenStreetMap's Overpass API
 * server-side — the browser can't call it directly (no CORS headers, see
 * comment on the query method below).
 *
 * HONESTY BOUNDARY: this returns REAL bank/branch names, addresses, and
 * locations from OpenStreetMap. It does NOT know which are NSFDC-authorised
 * Channel Partners (that list isn't publicly queryable — see class-level
 * comment in the frontend's channelPartners.js), and it does NOT know any
 * institution's real NPA/fund-utilization status (that's private data no
 * public source exposes). We classify by name pattern where confidently
 * possible (a branch literally named "State Bank of India" IS a PSB), and
 * for everything else we say so plainly rather than fabricate a status —
 * attaching a fake "high NPA" label to a real, named bank branch would
 * misrepresent an actual institution, which is a materially worse problem
 * than the entirely-fictional sample data this replaces for citizen-facing
 * research purposes.
 */
@RestController
@RequestMapping("/api/v2/credit-partners")
public class CreditPartnerController {

    private static final Logger LOG = LoggerFactory.getLogger(CreditPartnerController.class);
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(8))
            .build();
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final int MAX_RADIUS_KM = 25;
    private static final int DEFAULT_RADIUS_KM = 15;
    private static final int MAX_RESULTS = 20;

    private final GeoLabelService geoLabelService;
    private final PincodeGeocoder pincodeGeocoder;

    public CreditPartnerController(GeoLabelService geoLabelService,
                                    PincodeGeocoder pincodeGeocoder) {
        this.geoLabelService = geoLabelService;
        this.pincodeGeocoder = pincodeGeocoder;
    }

    // Real, well-known Indian Public Sector Bank names — a branch whose name
    // contains one of these IS genuinely a PSB, not a guess.
    private static final Set<String> PSB_NAMES = Set.of(
            "state bank of india", "punjab national bank", "bank of baroda", "canara bank",
            "union bank of india", "bank of india", "indian bank", "central bank of india",
            "uco bank", "indian overseas bank", "punjab & sind bank", "bank of maharashtra");

    private static String classify(String name) {
        if (name == null) return "Unclassified";
        String lower = name.toLowerCase();
        if (lower.contains("gramin bank") || lower.contains("grameena bank") || lower.contains("grameen bank")) {
            return "RRB";
        }
        for (String psb : PSB_NAMES) {
            if (lower.contains(psb)) return "PSB";
        }
        return "Unclassified"; // private/foreign banks, generic ATMs, etc. — not guessed as PSB/RRB
    }

    private static double haversineKm(double lat1, double lng1, double lat2, double lng2) {
        double r = 6371.0;
        double dLat = Math.toRadians(lat2 - lat1), dLng = Math.toRadians(lng2 - lng1);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
                + Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2))
                * Math.sin(dLng / 2) * Math.sin(dLng / 2);
        return r * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    /**
     * Accepts EITHER live coordinates or a PIN code. Geolocation used to be the
     * only way in, so a denied browser permission — or a desktop without GPS,
     * which is what a CSC operator is sitting at — killed the feature outright.
     * Coordinates win when both are supplied, since they're more precise than a
     * PIN code centroid.
     */
    @GetMapping("/nearby")
    public ResponseEntity<?> nearby(@RequestParam(required = false) Double lat,
                                     @RequestParam(required = false) Double lng,
                                     @RequestParam(required = false) String pincode,
                                     @RequestParam(defaultValue = "" + DEFAULT_RADIUS_KM) int radiusKm) {

        String pincodeLabel = null;
        if (lat == null || lng == null) {
            if (pincode == null || pincode.isBlank()) {
                return ResponseEntity.badRequest().body(Map.of(
                        "error", "Provide either lat and lng, or a 6-digit pincode"));
            }
            if (!PincodeGeocoder.isWellFormed(pincode)) {
                // Distinct from "we couldn't find it" — this one the citizen can fix by retyping.
                return ResponseEntity.badRequest().body(Map.of(
                        "error", "That doesn't look like an Indian PIN code — it should be 6 digits."));
            }
            var located = pincodeGeocoder.locate(pincode);
            if (located.isUnavailable()) {
                // Our lookup is down, not their mistake. Saying "we couldn't
                // find that PIN code" here would send someone to re-check a
                // PIN code that was correct all along.
                return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(Map.of(
                        "error", "The PIN code lookup is temporarily unavailable. Try again in a moment, "
                                + "or allow location access instead.",
                        "partners", List.of()));
            }
            if (!located.isFound()) {
                return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of(
                        "error", "We couldn't find that PIN code. Check it, or allow location access instead.",
                        "partners", List.of()));
            }
            lat = located.location().lat();
            lng = located.location().lng();
            pincodeLabel = located.location().label();
        }

        // Input validation — reject out-of-range coordinates rather than
        // silently forwarding garbage to an external API.
        if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
            return ResponseEntity.badRequest().body(Map.of("error", "Invalid lat/lng"));
        }
        int radius = Math.max(1, Math.min(radiusKm, MAX_RADIUS_KM));

        // Locale.US pins the decimal separator to '.' — without it, %f renders
        // with ',' under some container-default locales, which silently breaks
        // Overpass QL's around(radius,lat,lon) syntax and looks like a network error.
        String query = String.format(java.util.Locale.US,
                "[out:json][timeout:10];node[\"amenity\"=\"bank\"](around:%d,%f,%f);out %d;",
                radius * 1000, lat, lng, 60);

        try {
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create("https://overpass-api.de/api/interpreter"))
                    .timeout(Duration.ofSeconds(9))
                    .header("Content-Type", "application/x-www-form-urlencoded")
                    .POST(HttpRequest.BodyPublishers.ofString("data=" + java.net.URLEncoder.encode(query, "UTF-8")))
                    .build();
            HttpResponse<String> res = HTTP.send(req, HttpResponse.BodyHandlers.ofString());
            if (res.statusCode() != 200) {
                LOG.warn("Overpass returned status {} for query [{}]: {}", res.statusCode(), query,
                        res.body() != null && res.body().length() > 300 ? res.body().substring(0, 300) : res.body());
                return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                        .body(Map.of("error", "Bank-location lookup is temporarily unavailable", "partners", List.of()));
            }

            JsonNode root = MAPPER.readTree(res.body());
            List<Map<String, Object>> partners = new ArrayList<>();
            for (JsonNode el : root.path("elements")) {
                JsonNode tags = el.path("tags");
                String name = tags.path("name").asText(null);
                if (name == null || name.isBlank()) continue; // unnamed nodes aren't useful to show a citizen
                double plat = el.path("lat").asDouble();
                double plng = el.path("lon").asDouble();
                Map<String, Object> p = new HashMap<>();
                p.put("name", name);
                p.put("type", classify(name));
                p.put("lat", plat);
                p.put("lng", plng);
                p.put("distanceKm", Math.round(haversineKm(lat, lng, plat, plng) * 10) / 10.0);
                partners.add(p);
            }
            partners.sort(Comparator.comparingDouble(p -> (double) p.get("distanceKm")));
            List<Map<String, Object>> limited = partners.size() > MAX_RESULTS
                    ? partners.subList(0, MAX_RESULTS) : partners;

            // Best-effort — a citizen should see the bank list even if the
            // place-name lookup itself times out or fails. When they gave us a
            // PIN code, the forward lookup already returned the place name, so
            // reuse it rather than spending a second Nominatim call (and a
            // second chance to fail) reverse-geocoding what we just geocoded.
            String locationLabel = pincodeLabel != null ? pincodeLabel : geoLabelService.label(lat, lng);

            Map<String, Object> body = new HashMap<>();
            body.put("partners", limited);
            body.put("locationLabel", locationLabel);
            body.put("note", "Real bank locations from OpenStreetMap. \"Unclassified\" entries are not confirmed NSFDC Channel Partners. NSFDC authorisation and fund-utilization/NPA eligibility are not publicly available data — confirm directly with the branch.");
            return ResponseEntity.ok(body);
        } catch (Exception e) {
            LOG.warn("Overpass lookup failed for query [{}]: {}", query, e.toString());
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                    .body(Map.of("error", "Bank-location lookup is temporarily unavailable", "partners", List.of()));
        }
    }
}
