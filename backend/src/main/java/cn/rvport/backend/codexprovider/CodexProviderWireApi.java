package cn.rvport.backend.codexprovider;

public enum CodexProviderWireApi {
    RESPONSES("responses"),
    CHAT("chat");

    private final String codexValue;

    CodexProviderWireApi(String codexValue) {
        this.codexValue = codexValue;
    }

    public String codexValue() {
        return codexValue;
    }
}
