package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.notify.NotificationService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;

import java.lang.reflect.Constructor;
import java.util.Arrays;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Guards a failure mode that unit tests structurally cannot see.
 *
 * CreditApplicationService gained a second, test-only constructor. Spring will
 * auto-select a constructor only when there is exactly one; with two and no
 * {@code @Autowired} marker it stops guessing, looks for a no-arg constructor,
 * finds none, and fails the entire application context at startup. Every one of
 * the 243 unit tests still passed, because they all call the test constructor
 * directly and never ask Spring to build anything.
 *
 * That bug shipped and was caught only by booting the app. This is the cheap
 * standing check; a full {@code @SpringBootTest} would be better but needs a
 * live Mongo, which CI does not have.
 */
class SpringWiringTest {

    @ParameterizedTest
    @ValueSource(classes = {CreditApplicationService.class, NotificationService.class,
            CreditEligibilityService.class, PincodeGeocoder.class})
    void everyServiceGivesSpringExactlyOneConstructorToChoose(Class<?> type) {
        Constructor<?>[] constructors = type.getConstructors();
        assertTrue(constructors.length > 0, () -> type.getSimpleName() + " has no public constructor");

        if (constructors.length == 1) {
            return; // unambiguous — Spring uses it
        }

        long annotated = Arrays.stream(constructors)
                .filter(c -> c.isAnnotationPresent(Autowired.class))
                .count();
        assertEquals(1, annotated,
                () -> type.getSimpleName() + " has " + constructors.length + " public constructors but "
                        + annotated + " marked @Autowired. Spring needs exactly one, or the whole "
                        + "context fails to start.");
    }

    @Test
    void theServiceThatBrokeStartupStaysFixed() {
        Constructor<?> injected = Arrays.stream(CreditApplicationService.class.getConstructors())
                .filter(c -> c.isAnnotationPresent(Autowired.class))
                .findFirst()
                .orElseThrow(() -> new AssertionError(
                        "CreditApplicationService must mark its injection constructor @Autowired"));

        // The real one takes the notifier; the test one does not. If these ever
        // swap, Spring silently builds a service that notifies nobody.
        assertEquals(3, injected.getParameterCount());
    }
}
