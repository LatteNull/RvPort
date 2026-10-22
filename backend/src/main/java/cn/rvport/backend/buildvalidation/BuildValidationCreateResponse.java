package cn.rvport.backend.buildvalidation;

import java.util.List;

public record BuildValidationCreateResponse(
        List<BuildValidationResponse> builds
) {
}
