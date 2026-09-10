package com.yojnasetu.gateway.notify;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * The citizen's (or rep's) notification inbox.
 *
 * Authenticated, and always scoped to the caller — the recipient comes from
 * the JWT principal, never from a parameter, so one person's inbox can't be
 * requested by another.
 */
@RestController
@RequestMapping("/api/v2/notifications")
public class NotificationController {

    private final NotificationService notificationService;

    public NotificationController(NotificationService notificationService) {
        this.notificationService = notificationService;
    }

    @GetMapping
    public List<Notification> inbox(Authentication auth) {
        return notificationService.inbox(auth.getName());
    }

    /** For the unread badge — cheap enough to poll. */
    @GetMapping("/unread-count")
    public Map<String, Long> unreadCount(Authentication auth) {
        return Map.of("unread", notificationService.unreadCount(auth.getName()));
    }

    @PostMapping("/{id}/read")
    public ResponseEntity<?> markRead(Authentication auth, @PathVariable String id) {
        boolean marked = notificationService.markRead(auth.getName(), id);
        // 404 rather than 403 when it isn't theirs — confirming the id exists
        // would leak that someone else holds it, same rule as applications.
        return marked
                ? ResponseEntity.ok(Map.of("read", true))
                : ResponseEntity.status(404).body(Map.of("error", "Notification not found"));
    }
}
