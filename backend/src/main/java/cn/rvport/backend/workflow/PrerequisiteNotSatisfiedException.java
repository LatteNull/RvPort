package cn.rvport.backend.workflow;

import cn.rvport.backend.common.error.ApiException;
import java.util.Map;
import org.springframework.http.HttpStatus;

public class PrerequisiteNotSatisfiedException extends ApiException {

    public PrerequisiteNotSatisfiedException(String stageId, StagePrerequisiteResponse prerequisite) {
        super(
                HttpStatus.CONFLICT,
                "PREREQUISITE_NOT_SATISFIED",
                "当前阶段前置条件不满足",
                Map.of(
                        "stageId", stageId,
                        "prerequisite", prerequisite
                )
        );
    }
}
