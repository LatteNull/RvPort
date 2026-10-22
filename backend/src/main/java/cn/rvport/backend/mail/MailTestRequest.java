package cn.rvport.backend.mail;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

public record MailTestRequest(
        @Email @NotBlank String to,
        @Valid MailSettingsRequest settings
) {
}
