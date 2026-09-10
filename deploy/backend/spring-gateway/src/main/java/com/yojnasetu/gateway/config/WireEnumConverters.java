package com.yojnasetu.gateway.config;

import com.yojnasetu.gateway.credit.ChannelPartnerType;
import com.yojnasetu.gateway.credit.ConsentPurpose;
import com.yojnasetu.gateway.credit.CreditApplicationStatus;
import com.yojnasetu.gateway.credit.MoratoriumMode;
import com.yojnasetu.gateway.credit.ReasonCode;
import com.yojnasetu.gateway.credit.RepType;
import com.yojnasetu.gateway.credit.VerificationMode;
import org.springframework.context.annotation.Configuration;
import org.springframework.format.FormatterRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Teaches Spring MVC to read this module's enums from path variables and query
 * parameters using their wire names.
 *
 * {@code @JsonCreator} governs only request BODIES. Path variables and query
 * parameters go through Spring's ConversionService, which falls back to
 * {@code Enum.valueOf} — so {@code ?status=under_verification} and
 * {@code DELETE /consents/partner_sharing} both failed with a 400, while the
 * identical value inside a JSON body parsed fine. The split is easy to miss
 * precisely because half the API works.
 *
 * Registering the same {@code fromWire} methods here means there is one
 * spelling rule for each enum across the whole API rather than two, and an
 * unknown value is still rejected rather than silently defaulted.
 */
@Configuration
public class WireEnumConverters implements WebMvcConfigurer {

    @Override
    public void addFormatters(FormatterRegistry registry) {
        registry.addConverter(String.class, ConsentPurpose.class, ConsentPurpose::fromWire);
        registry.addConverter(String.class, CreditApplicationStatus.class, CreditApplicationStatus::fromWire);
        registry.addConverter(String.class, ChannelPartnerType.class, ChannelPartnerType::fromWire);
        registry.addConverter(String.class, ReasonCode.class, ReasonCode::fromWire);
        registry.addConverter(String.class, MoratoriumMode.class, MoratoriumMode::fromWire);
        registry.addConverter(String.class, VerificationMode.class, VerificationMode::fromWire);
        registry.addConverter(String.class, RepType.class, RepType::fromWire);
    }
}
