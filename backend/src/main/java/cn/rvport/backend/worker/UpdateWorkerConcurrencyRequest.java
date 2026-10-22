package cn.rvport.backend.worker;

import jakarta.validation.constraints.Min;

public record UpdateWorkerConcurrencyRequest(
        @Min(0) Integer concurrencyLimit
) {
}
