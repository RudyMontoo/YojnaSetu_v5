package com.yojnasetu.gateway.security;

import com.yojnasetu.gateway.util.ClientIp;
import io.github.bucket4j.Bandwidth;
import io.github.bucket4j.Bucket;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 60 requests/min per IP for general endpoints, per CLAUDE.md's L3 security
 * layer. OTP-specific tighter limits (5/hour per phone) live in
 * OtpService, not here — this filter is the coarse per-IP backstop, not
 * the phone-specific abuse guard.
 *
 * Identity comes from ClientIp (X-Real-IP, set by our nginx) — NOT from
 * X-Forwarded-For[0], which any client can set and which made this filter
 * trivially bypassable by rotating the header.
 */
@Component
public class RateLimitFilter extends OncePerRequestFilter {

    /** Hard cap on tracked IPs. Buckets are ~100 bytes, so 100k ≈ 10MB — bounded.
     *  Without a cap the map is an unbounded memory leak: under CGNAT a single
     *  operator legitimately presents thousands of distinct addresses, and the map
     *  never evicted anything. On overflow we clear rather than evict-LRU: losing
     *  the counters briefly is a far smaller problem than an OOM, and a full map
     *  only happens under genuinely abnormal traffic. */
    private static final int MAX_TRACKED_IPS = 100_000;

    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

    private Bucket newBucket() {
        return Bucket.builder()
                .addLimit(Bandwidth.classic(60, io.github.bucket4j.Refill.intervally(60, Duration.ofMinutes(1))))
                .build();
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        String ip = clientIp(req);
        if (buckets.size() >= MAX_TRACKED_IPS) {
            buckets.clear();
        }
        Bucket bucket = buckets.computeIfAbsent(ip, k -> newBucket());

        if (bucket.tryConsume(1)) {
            chain.doFilter(req, res);
        } else {
            res.setStatus(429);
            res.setHeader("Retry-After", "60");
            res.setContentType("application/json");
            res.getWriter().write("{\"error\":\"RATE_LIMITED\"}");
        }
    }

    private String clientIp(HttpServletRequest req) {
        return ClientIp.of(req);
    }
}
