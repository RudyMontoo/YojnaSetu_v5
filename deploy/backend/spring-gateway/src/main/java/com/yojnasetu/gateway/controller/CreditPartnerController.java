package com.yojnasetu.gateway.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.yojnasetu.gateway.credit.ChannelPartnerType;
import com.yojnasetu.gateway.credit.CreditProduct;
import com.yojnasetu.gateway.credit.CreditProductRepository;
import com.yojnasetu.gateway.credit.PincodeGeocoder;
import com.yojnasetu.gateway.service.GeoLabelService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
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
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

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
    private final CreditProductRepository creditProducts;

    /**
     * Overpass is a free, shared community API with no SLA and a real
     * rate-limit — a demo where several people search near-identical
     * locations in the same few minutes is exactly the traffic pattern that
     * trips it. Bank branches don't move minute to minute, so caching the
     * raw OSM result (name/lat/lng only, before any scheme-specific
     * filtering) for a short window turns N identical demo-day queries into
     * one real Overpass call. Coordinates are snapped to a ~1km grid so
     * nearby requests for "the same place" share a cache entry even when the
     * lat/lng differ in the fourth decimal. Failures are never cached — see
     * PincodeGeocoder for the same rule and the same reason.
     */
    private final Map<String, CacheEntry> overpassCache = new ConcurrentHashMap<>();

    @Value("${app.overpass.cache-ttl-minutes:20}")
    private long cacheTtlMinutes;

    private record RawPartner(String name, double lat, double lng) {
    }

    private record CacheEntry(List<RawPartner> partners, Instant fetchedAt) {
    }

    public CreditPartnerController(GeoLabelService geoLabelService,
                                    PincodeGeocoder pincodeGeocoder,
                                    CreditProductRepository creditProducts) {
        this.geoLabelService = geoLabelService;
        this.pincodeGeocoder = pincodeGeocoder;
        this.creditProducts = creditProducts;
    }

    // Real, well-known Indian Public Sector Bank names — a branch whose name
    // contains one of these IS genuinely a PSB, not a guess.
    private static final Set<String> PSB_NAMES = Set.of(
            "state bank of india", "punjab national bank", "bank of baroda", "canara bank",
            "union bank of india", "bank of india", "indian bank", "central bank of india",
            "uco bank", "indian overseas bank", "punjab & sind bank", "bank of maharashtra");

    private static ChannelPartnerType classify(String name) {
        if (name == null) return ChannelPartnerType.UNCLASSIFIED;
        String lower = name.toLowerCase();
        if (lower.contains("gramin bank") || lower.contains("grameena bank") || lower.contains("grameen bank")) {
            return ChannelPartnerType.RRB;
        }
        for (String psb : PSB_NAMES) {
            if (lower.contains(psb)) return ChannelPartnerType.PSB;
        }
        // private/foreign banks, generic ATMs, etc. — not guessed as PSB/RRB
        return ChannelPartnerType.UNCLASSIFIED;
    }

    /**
     * @return TRUE when this branch's type is a channel for the scheme, FALSE
     *         when it provably is not, and null when the branch's type could
     *         not be determined at all.
     */
    private static Boolean deliversScheme(ChannelPartnerType type, CreditProduct scheme) {
        if (type == ChannelPartnerType.UNCLASSIFIED) {
            return null; // we don't know what this is, so we don't get to say
        }
        List<ChannelPartnerType> channels = scheme.getChannelPartnerTypes();
        if (channels == null || channels.isEmpty()) {
            return null; // no channel data for the scheme — same honesty rule
        }
        return channels.contains(type);
    }

    /** Confirmed channel (0) before unknown (1) before provably-not (2). */
    private static int deliveryRank(Object deliversScheme) {
        if (deliversScheme == null) return 1;
        return Boolean.TRUE.equals(deliversScheme) ? 0 : 2;
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
                                     @RequestParam(required = false) String schemeId,
                                     @RequestParam(defaultValue = "" + DEFAULT_RADIUS_KM) int radiusKm) {

        CreditProduct scheme = null;
        if (schemeId != null && !schemeId.isBlank()) {
            scheme = creditProducts.findById(schemeId).filter(CreditProduct::isActive).orElse(null);
            if (scheme == null) {
                return ResponseEntity.badRequest().body(Map.of(
                        "error", "Unknown schemeId: " + schemeId));
            }
        }

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

        List<RawPartner> raw = fetchNearbyBanks(lat, lng, radius);
        if (raw == null) {
            return lookupUnavailable(scheme);
        }

        List<Map<String, Object>> partners = new ArrayList<>();
        for (RawPartner rp : raw) {
            ChannelPartnerType type = classify(rp.name());
            Map<String, Object> p = new HashMap<>();
            p.put("name", rp.name());
            p.put("type", type.wireName());
            p.put("lat", rp.lat());
            p.put("lng", rp.lng());
            p.put("distanceKm", Math.round(haversineKm(lat, lng, rp.lat(), rp.lng()) * 10) / 10.0);
            // Three-state on purpose. true = this type is a channel for the
            // chosen scheme; false = it provably is not; null = we could not
            // determine the branch's type, so we say nothing. Collapsing
            // null into false would tell a citizen a real branch can't help
            // them when we simply don't know.
            p.put("deliversScheme", scheme == null ? null : deliversScheme(type, scheme));
            partners.add(p);
        }
        // Confirmed channels first, then unknowns, then the ones that
        // provably can't process this scheme — distance within each group.
        // A nearer branch that cannot deliver the loan is not more useful
        // than a further one that can.
        partners.sort(Comparator
                .comparingInt((Map<String, Object> p) -> deliveryRank(p.get("deliversScheme")))
                .thenComparingDouble(p -> (double) p.get("distanceKm")));
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

        // Same guidance whether or not the branch lookup succeeded — a
        // State Channelising Agency never appears in these results, so an
        // otherwise-empty list must still point somewhere real.
        addSchemeGuidance(body, scheme);
        return ResponseEntity.ok(body);
    }

    /**
     * Grid key for the cache: coordinates rounded to 2 decimal places is
     * roughly a 1.1km square at Indian latitudes — small next to the
     * 1-25km search radius, so two citizens searching "the same area" of a
     * demo venue land on the same cache entry without merging genuinely
     * different locations.
     */
    private String cacheKey(double lat, double lng, int radiusKm) {
        return String.format(Locale.US, "%.2f,%.2f,%d", lat, lng, radiusKm);
    }

    /** Returns raw OSM bank nodes (cached when fresh), or null when the lookup failed. */
    private List<RawPartner> fetchNearbyBanks(double lat, double lng, int radiusKm) {
        String key = cacheKey(lat, lng, radiusKm);
        CacheEntry cached = overpassCache.get(key);
        if (cached != null
                && cached.fetchedAt().plus(Duration.ofMinutes(cacheTtlMinutes)).isAfter(Instant.now())) {
            return cached.partners();
        }

        // Locale.US pins the decimal separator to '.' — without it, %f renders
        // with ',' under some container-default locales, which silently breaks
        // Overpass QL's around(radius,lat,lon) syntax and looks like a network error.
        String query = String.format(Locale.US,
                "[out:json][timeout:10];node[\"amenity\"=\"bank\"](around:%d,%f,%f);out %d;",
                radiusKm * 1000, lat, lng, 60);

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
                return null;
            }

            JsonNode root = MAPPER.readTree(res.body());
            List<RawPartner> partners = new ArrayList<>();
            for (JsonNode el : root.path("elements")) {
                JsonNode tags = el.path("tags");
                String name = tags.path("name").asText(null);
                if (name == null || name.isBlank()) continue; // unnamed nodes aren't useful to show a citizen
                partners.add(new RawPartner(name, el.path("lat").asDouble(), el.path("lon").asDouble()));
            }
            overpassCache.put(key, new CacheEntry(partners, Instant.now()));
            return partners;
        } catch (Exception e) {
            LOG.warn("Overpass lookup failed for query [{}]: {}", query, e.toString());
            return null;
        }
    }

    /**
     * OpenStreetMap is down or rate-limiting us, so we have no branches. That
     * does NOT mean we have nothing to say: if the citizen picked a scheme, the
     * channels it runs through are still known and still true, and for schemes
     * delivered by State Channelising Agencies the branch list was never the
     * useful answer anyway. Withholding that because a third-party map service
     * is unavailable would turn a partial outage into a dead end.
     */
    private static ResponseEntity<?> lookupUnavailable(CreditProduct scheme) {
        Map<String, Object> body = new HashMap<>();
        body.put("error", "Bank-location lookup is temporarily unavailable");
        body.put("partners", List.of());
        addSchemeGuidance(body, scheme);
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(body);
    }

    /**
     * Attaches what we know about how a scheme is delivered — including the
     * channels a bank-branch search structurally cannot surface.
     */
    private static void addSchemeGuidance(Map<String, Object> body, CreditProduct scheme) {
        if (scheme == null) {
            return;
        }
        body.put("schemeId", scheme.getId());
        body.put("schemeName", scheme.getName());
        body.put("schemeChannels", scheme.getChannelPartnerTypes());

        List<String> offMap = scheme.getChannelPartnerTypes() == null ? List.of()
                : scheme.getChannelPartnerTypes().stream()
                        .filter(t -> !t.appearsInOpenStreetMap())
                        .map(ChannelPartnerType::label)
                        .toList();
        if (!offMap.isEmpty()) {
            body.put("channelsNotOnMap", offMap);
            body.put("schemeNote", offMapNote(scheme, offMap));
        }
    }

    private static String offMapNote(CreditProduct scheme, List<String> offMap) {
        boolean everyChannelIsOffMap = offMap.size() == scheme.getChannelPartnerTypes().size();
        // "also" would be a lie for a scheme like Aajeevika, whose only channel
        // is an NBFC-MFI — there is no on-map alternative it is "also" besides.
        String opening = scheme.getName() + (everyChannelIsOffMap ? " is delivered through " : " is also delivered through ");

        StringBuilder note = new StringBuilder(opening)
                .append(String.join(", ", offMap))
                .append(". These don't appear in a bank-branch search — ask at a CSC");

        // Only claim a cheaper route when it genuinely is one. A State
        // Channelising Agency is the concessional channel (6.5%, or 4% for the
        // women's scheme); an NBFC-MFI charges 15% for the same money. Telling
        // a citizen the MFI route "often costs less than a bank" would send
        // them to the single most expensive door there is.
        if (scheme.getChannelPartnerTypes().contains(ChannelPartnerType.SCA)) {
            note.append(" or your State SC Development Corporation, which usually lends at the "
                    + "scheme's lowest rate");
        }
        return note.append('.').toString();
    }
}
