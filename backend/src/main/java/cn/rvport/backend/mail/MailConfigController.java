package cn.rvport.backend.mail;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class MailConfigController {

    private final MailConfigService mailConfigService;
    private final MailDeliveryService mailDeliveryService;

    public MailConfigController(MailConfigService mailConfigService, MailDeliveryService mailDeliveryService) {
        this.mailConfigService = mailConfigService;
        this.mailDeliveryService = mailDeliveryService;
    }

    @GetMapping("/api/admin/configs/mail")
    public ApiResponse<MailSettingsResponse> get(HttpServletRequest request) {
        return ApiResponse.ok(mailConfigService.currentSettings(), TraceIdFilter.currentTraceId(request));
    }

    @PatchMapping("/api/admin/configs/mail")
    public ApiResponse<MailSettingsResponse> update(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @Valid @RequestBody MailSettingsRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(mailConfigService.update(body, principal.id()), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/admin/configs/mail:test")
    public ApiResponse<MailSendResult> test(
            @Valid @RequestBody MailTestRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(mailDeliveryService.sendTest(body.to(), body.settings()), TraceIdFilter.currentTraceId(request));
    }
}
