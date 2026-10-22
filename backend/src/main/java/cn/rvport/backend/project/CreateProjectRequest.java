package cn.rvport.backend.project;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record CreateProjectRequest(
        @NotBlank @Size(max = 160) String name,
        @Size(max = 2000) String description,
        @Size(max = 32) String sourceArch,
        @Size(max = 32) String targetArch
) {
}
