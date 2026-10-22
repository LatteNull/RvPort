package cn.rvport.backend.source.deploy;

import java.util.List;

public record SourceDeployCreateResponse(
        List<SourceDeployResponse> deployments
) {
}
