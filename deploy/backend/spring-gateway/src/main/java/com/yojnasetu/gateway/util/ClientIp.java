package com.yojnasetu.gateway.util;

import jakarta.servlet.http.HttpServletRequest;

/**
 * The single source of truth for "who is calling". Rate limiting and the DPDP
 * audit trail both key on this, so getting it wrong is a security bug, not a
 * cosmetic one.
 *
 * Why not X-Forwarded-For[0]: a client can send its own XFF header, and neither
 * our nginx ($proxy_add_x_forwarded_for) nor Azure's ingress replaces it — they
 * APPEND. So the header reads [attacker junk..., real client]: the first entry is
 * whatever the attacker typed and the last is the truth. Keying on [0] let anyone
 * evade every rate limit by rotating the header, and forge audit_log entries.
 *
 * nginx now resolves the real client via the realip module (recursion off = take
 * the last hop) and passes it as X-Real-IP, overwriting any client-supplied value.
 * That header is therefore trustworthy and XFF is not; we read X-Real-IP only and
 * deliberately do NOT fall back to XFF, since a fallback is exactly the bypass we
 * are closing. If the header is absent (direct hit, not through nginx) the socket
 * address is already the real peer.
 */
public final class ClientIp {

    private ClientIp() {}

    public static String of(HttpServletRequest req) {
        String realIp = req.getHeader("X-Real-IP");
        if (realIp != null && !realIp.isBlank()) {
            return realIp.trim();
        }
        return req.getRemoteAddr();
    }
}
