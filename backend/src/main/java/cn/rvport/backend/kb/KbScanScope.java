package cn.rvport.backend.kb;

import java.util.List;

public record KbScanScope(
        String mode,
        List<String> paths
) {
}
