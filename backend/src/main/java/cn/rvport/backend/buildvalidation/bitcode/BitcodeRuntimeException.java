package cn.rvport.backend.buildvalidation.bitcode;

public class BitcodeRuntimeException extends IllegalArgumentException {

    private final BitcodeReasonCode reasonCode;
    private final BitcodeVerificationFailure failure;

    public BitcodeRuntimeException(BitcodeReasonCode reasonCode, String message) {
        this(reasonCode, message, null);
    }

    public BitcodeRuntimeException(BitcodeReasonCode reasonCode, String message, Throwable cause) {
        super(message, cause);
        this.reasonCode = reasonCode;
        this.failure = null;
    }

    public BitcodeRuntimeException(BitcodeVerificationFailure failure, Throwable cause) {
        super(failure.message(), cause);
        this.reasonCode = failure.reasonCode();
        this.failure = failure;
    }

    public BitcodeReasonCode reasonCode() {
        return reasonCode;
    }

    public BitcodeVerificationFailure failure() {
        return failure;
    }
}
