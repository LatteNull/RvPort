package cn.rvport.backend.mail;

public record MailSendResult(
        boolean success,
        String message
) {
    public static MailSendResult success(String message) {
        return new MailSendResult(true, message);
    }

    public static MailSendResult failure(String message) {
        return new MailSendResult(false, message);
    }
}
