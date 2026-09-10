package com.yojnasetu.gateway.credit;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.regex.Pattern;

/**
 * Turns an Indian PIN code into coordinates, so the partner locator works for
 * someone who won't or can't share their live location.
 *
 * Geolocation was the locator's only input path, which meant a denied browser
 * permission — or simply a desktop without GPS — killed the feature outright.
 * Plenty of citizens will be helped at a CSC on someone else's machine, so
 * "type your PIN code" is the difference between the feature working and not.
 *
 * Uses the same Nominatim service GeoLabelService already proxies, for the
 * same reason: no CORS headers for browser calls, and its usage policy
 * requires an identifying User-Agent.
 */
@Service
public class PincodeGeocoder {

    private static final Logger LOG = LoggerFactory.getLogger(PincodeGeocoder.class);

    /**
     * Indian PIN codes are exactly six digits and never begin with zero — the
     * first digit is the postal region, numbered 1–9. Rejecting the malformed
     * ones here avoids a pointless round trip to Nominatim.
     */
    private static final Pattern INDIAN_PINCODE = Pattern.compile("[1-9][0-9]{5}");

    // Nominatim is a free, heavily-loaded community service and is regularly
    // slow from here — 5s/6s produced connect timeouts on PIN codes that
    // resolve fine when given room. Being slow is not the same as being wrong,
    // and the citizen pays for the difference.
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();
    private static final ObjectMapper MAPPER = new ObjectMapper();

    /**
     * PIN code centroids do not move, so a successful lookup is cached for the
     * process lifetime. This also keeps us inside Nominatim's 1-request-per-
     * second usage policy when a demo audience all types the same PIN code.
     * Failures are deliberately NOT cached — a timeout must not become a
     * permanent "we couldn't find it" for that code.
     */
    private final Map<String, Location> cache = new ConcurrentHashMap<>();

    public static boolean isWellFormed(String pincode) {
        return pincode != null && INDIAN_PINCODE.matcher(pincode.trim()).matches();
    }

    /**
     * Resolves a PIN code, distinguishing the three outcomes that matter.
     *
     * "We couldn't find that PIN code" and "our lookup is down" read
     * identically in code if both are an empty Optional, but they are opposite
     * messages to a citizen: one says *you* typed something wrong, the other
     * says *we* are broken. Telling someone their real PIN code doesn't exist
     * because a third-party service was slow is the kind of small lie this
     * module is supposed to avoid.
     */
    public GeocodeResult locate(String pincode) {
        if (!isWellFormed(pincode)) {
            return GeocodeResult.notFound();
        }
        String trimmed = pincode.trim();

        Location cached = cache.get(trimmed);
        if (cached != null) {
            return GeocodeResult.found(cached);
        }

        try {
            String url = "https://nominatim.openstreetmap.org/search"
                    + "?format=jsonv2&countrycodes=in&limit=1&addressdetails=1&postalcode=" + trimmed;
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .timeout(Duration.ofSeconds(12))
                    .header("User-Agent",
                            "YojnaSarthi/1.0 (welfare-scheme discovery app; contact: rudra@yojnasetu.in)")
                    .GET()
                    .build();

            HttpResponse<String> res = HTTP.send(req, HttpResponse.BodyHandlers.ofString());
            if (res.statusCode() != 200) {
                LOG.warn("Nominatim returned {} for pincode {}", res.statusCode(), trimmed);
                return GeocodeResult.unavailable();
            }

            JsonNode results = MAPPER.readTree(res.body());
            if (!results.isArray() || results.isEmpty()) {
                // A real answer from Nominatim: well-formed, but not in use.
                return GeocodeResult.notFound();
            }

            JsonNode hit = results.get(0);
            double lat = hit.path("lat").asDouble();
            double lng = hit.path("lon").asDouble();
            if (lat == 0 && lng == 0) {
                return GeocodeResult.notFound();
            }

            Location location = new Location(lat, lng, placeName(hit), trimmed);
            cache.put(trimmed, location);
            return GeocodeResult.found(location);

        } catch (Exception e) {
            // Timeout, DNS, connection reset — our problem, not the citizen's.
            LOG.warn("Pincode lookup unavailable for {}: {}", trimmed, e.toString());
            return GeocodeResult.unavailable();
        }
    }

    /** Outcome of a lookup. {@code location} is present only when FOUND. */
    public record GeocodeResult(Status status, Location location) {

        public enum Status { FOUND, NOT_FOUND, UNAVAILABLE }

        static GeocodeResult found(Location location) {
            return new GeocodeResult(Status.FOUND, location);
        }

        static GeocodeResult notFound() {
            return new GeocodeResult(Status.NOT_FOUND, null);
        }

        static GeocodeResult unavailable() {
            return new GeocodeResult(Status.UNAVAILABLE, null);
        }

        public boolean isFound() {
            return status == Status.FOUND;
        }

        public boolean isUnavailable() {
            return status == Status.UNAVAILABLE;
        }
    }

    private static String placeName(JsonNode hit) {
        JsonNode addr = hit.path("address");
        String city = firstNonBlank(addr, "city", "town", "village", "suburb", "county", "state_district");
        String state = addr.path("state").asText(null);
        if (city != null && state != null) {
            return city + ", " + state;
        }
        if (state != null) {
            return state;
        }
        String display = hit.path("display_name").asText(null);
        return display != null && !display.isBlank() ? display : null;
    }

    private static String firstNonBlank(JsonNode node, String... fields) {
        for (String field : fields) {
            String value = node.path(field).asText(null);
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return null;
    }

    public record Location(double lat, double lng, String label, String pincode) {
    }
}
