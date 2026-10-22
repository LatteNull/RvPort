package cn.rvport.backend.mail;

import cn.rvport.backend.common.error.ApiException;
import java.util.Properties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.mail.MailException;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSenderImpl;
import org.springframework.stereotype.Service;

@Service
public class MailDeliveryService {

    private static final Logger log = LoggerFactory.getLogger(MailDeliveryService.class);

    private final MailConfigService mailConfigService;
    private final java.util.function.Function<MailConfig, JavaMailSenderImpl> senderFactory;

    @Autowired
    public MailDeliveryService(MailConfigService mailConfigService) {
        this(mailConfigService, null);
    }

    MailDeliveryService(
            MailConfigService mailConfigService,
            java.util.function.Function<MailConfig, JavaMailSenderImpl> senderFactory
    ) {
        this.mailConfigService = mailConfigService;
        this.senderFactory = senderFactory == null ? this::sender : senderFactory;
    }

    public MailSendResult sendTest(String to, MailSettingsRequest temporarySettings) {
        MailConfig config = temporarySettings == null
                ? mailConfigService.currentConfig()
                : merge(mailConfigService.currentConfig(), temporarySettings);
        try {
            send(config, to, "RvPort 邮箱配置测试", "这是一封 RvPort 邮箱配置测试邮件。");
            return MailSendResult.success("测试邮件发送成功");
        } catch (ApiException ex) {
            return MailSendResult.failure(ex.getMessage());
        }
    }

    public MailSendResult sendInvitation(String to, String username, String url) {
        return sendConfigured(to, "RvPort 账号邀请", """
                你好，

                管理员已为你创建 RvPort 账号：%s

                请打开下面的链接设置密码并完成注册：
                %s

                如果你没有预期收到这封邮件，请忽略。
                """.formatted(username, url));
    }

    public MailSendResult sendPasswordReset(String to, String url) {
        return sendConfigured(to, "RvPort 密码重置", """
                你好，

                请打开下面的链接设置新的 RvPort 登录密码：
                %s

                如果你没有发起密码重置，请忽略。
                """.formatted(url));
    }

    public MailSendResult sendTaskCompleted(String to, String subject, String body) {
        return sendConfigured(to, subject, body);
    }

    private MailSendResult sendConfigured(String to, String subject, String body) {
        try {
            send(mailConfigService.currentConfig(), to, subject, body);
            return MailSendResult.success("邮件发送成功");
        } catch (ApiException ex) {
            log.warn("Mail send skipped or failed: {}", ex.getMessage());
            return MailSendResult.failure(ex.getMessage());
        }
    }

    private void send(MailConfig config, String to, String subject, String body) {
        mailConfigService.validateSendable(config);
        if (config.testMode()) {
            log.info("Mail test mode message to={} subject={}", to, subject);
            return;
        }
        try {
            JavaMailSenderImpl sender = senderFactory.apply(config);
            SimpleMailMessage message = new SimpleMailMessage();
            message.setFrom(config.fromAddress());
            message.setTo(to);
            message.setSubject(subject);
            message.setText(body);
            sender.send(message);
        } catch (MailException ex) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "MAIL_SEND_FAILED", sanitize(ex));
        }
    }

    JavaMailSenderImpl sender(MailConfig config) {
        JavaMailSenderImpl sender = new JavaMailSenderImpl();
        sender.setHost(config.host());
        sender.setPort(config.port());
        sender.setUsername(config.username());
        sender.setPassword(config.password());
        Properties properties = sender.getJavaMailProperties();
        properties.put("mail.smtp.auth", String.valueOf(config.username() != null && !config.username().isBlank()));
        properties.put("mail.smtp.starttls.enable", String.valueOf(config.startTls()));
        properties.put("mail.smtp.ssl.enable", String.valueOf(config.ssl()));
        properties.put("mail.smtp.connectiontimeout", String.valueOf(config.connectionTimeoutMillis()));
        properties.put("mail.smtp.timeout", String.valueOf(config.readTimeoutMillis()));
        return sender;
    }

    private MailConfig merge(MailConfig current, MailSettingsRequest request) {
        return new MailConfig(
                value(request.enabled(), current.enabled()),
                value(request.testMode(), current.testMode()),
                value(request.host(), current.host()),
                value(request.port(), current.port()),
                value(request.username(), current.username()),
                request.password() == null || request.password().isBlank() ? current.password() : request.password(),
                value(request.fromAddress(), current.fromAddress()),
                value(request.startTls(), current.startTls()),
                value(request.ssl(), current.ssl()),
                value(request.connectionTimeoutMillis(), current.connectionTimeoutMillis()),
                value(request.readTimeoutMillis(), current.readTimeoutMillis()),
                value(request.frontendBaseUrl(), current.frontendBaseUrl())
        );
    }

    private String sanitize(Exception ex) {
        String message = ex.getMessage();
        if (message == null || message.isBlank()) {
            return "邮件发送失败";
        }
        return message.replaceAll("(?i)(password|token|secret)=\\S+", "$1=******");
    }

    private boolean value(Boolean value, boolean fallback) {
        return value == null ? fallback : value;
    }

    private int value(Integer value, int fallback) {
        return value == null ? fallback : value;
    }

    private String value(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }
}
