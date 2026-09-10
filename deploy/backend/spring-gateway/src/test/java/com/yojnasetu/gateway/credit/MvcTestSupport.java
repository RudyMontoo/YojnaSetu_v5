package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.config.WireEnumConverters;
import org.springframework.format.support.DefaultFormattingConversionService;
import org.springframework.format.support.FormattingConversionService;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.List;

/**
 * Shared wiring for the controller tests.
 *
 * These run standalone rather than through a full Spring context, so they need
 * no Mongo and stay fast enough to run on every push. The important detail is
 * {@link #conversionService()}: the same WireEnumConverters the application
 * registers are installed here too. Without them these tests would bind
 * parameters differently from production and would sail past exactly the bug
 * they exist to catch — {@code ?status=under_verification} returning 400
 * because @JsonCreator does not apply to query parameters.
 *
 * What they deliberately do NOT cover is the security filter chain: standalone
 * setup has no SecurityConfig, so role gating and the 403-vs-404 rules are not
 * exercised here and still need verifying against a running app.
 */
final class MvcTestSupport {

    private MvcTestSupport() {
    }

    static FormattingConversionService conversionService() {
        DefaultFormattingConversionService conversion = new DefaultFormattingConversionService();
        new WireEnumConverters().addFormatters(conversion);
        return conversion;
    }

    static MockMvc mvc(Object controller) {
        // Standalone setup does not auto-register Jackson the way a full
        // Spring context does — without this, every JSON body/response comes
        // back as a plain String and every jsonPath assertion fails.
        return MockMvcBuilders.standaloneSetup(controller)
                .setConversionService(conversionService())
                .setMessageConverters(new MappingJackson2HttpMessageConverter())
                .build();
    }

    /**
     * A logged-in principal. Controllers read the owner from here and never
     * from the request body, so the tests must supply it the same way.
     */
    static Authentication as(String userId, String role) {
        return new UsernamePasswordAuthenticationToken(userId, null,
                List.of(new SimpleGrantedAuthority("ROLE_" + role)));
    }

    static Authentication citizen() {
        return as("citizen-1", "CITIZEN");
    }

    static Authentication rep() {
        return as("rep-9", "BRANCH_REP");
    }

    static Authentication admin() {
        return as("admin-1", "ADMIN");
    }
}
