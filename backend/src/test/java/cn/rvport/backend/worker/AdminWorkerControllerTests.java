package cn.rvport.backend.worker;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class AdminWorkerControllerTests {

    @Test
    void delegatesListGetAndConcurrencyUpdate() {
        WorkerManagementService service = mock(WorkerManagementService.class);
        AdminWorkerController controller = new AdminWorkerController(service);
        MockHttpServletRequest request = new MockHttpServletRequest();

        assertThat(controller.list(null, request).timestamp()).isNotNull();
        assertThat(controller.get("worker-1", request).timestamp()).isNotNull();
        assertThat(controller.updateConcurrency("worker-1", null, request).timestamp()).isNotNull();

        verify(service).list(null);
        verify(service).get("worker-1");
        verify(service).updateConcurrency("worker-1", null);
    }
}
