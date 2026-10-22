package cn.rvport.backend.source;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.web.multipart.MultipartFile;

class SourceControllerTests {

    @Test
    void delegatesSourceAndRecheckEndpoints() {
        SourceService sourceService = mock(SourceService.class);
        SourceCompareService compareService = mock(SourceCompareService.class);
        SourceController controller = new SourceController(sourceService, compareService);
        RvPortUserPrincipal principal = principal();
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID recheckId = UUID.randomUUID();
        UUID diffId = UUID.randomUUID();
        MultipartFile file = mock(MultipartFile.class);
        MockHttpServletRequest request = new MockHttpServletRequest();

        assertThat(controller.list(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.latestCompare(principal, projectId, request).timestamp()).isNotNull();
        assertThat(controller.createRecheck(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.createLatestRecheck(principal, projectId, request).timestamp()).isNotNull();
        assertThat(controller.diffItems(principal, recheckId, null, request).timestamp()).isNotNull();
        assertThat(controller.diffItem(principal, recheckId, diffId, request).timestamp()).isNotNull();
        assertThat(controller.uploadArchive(principal, projectId, file, "v1", "note", true, request).timestamp()).isNotNull();
        assertThat(controller.gitSync(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.activate(principal, projectId, revisionId, request).timestamp()).isNotNull();

        verify(sourceService).uploadArchive(projectId, file, "v1", "note", true, principal.id(), false, request);
        verify(sourceService).gitSync(projectId, null, principal.id(), false, request);
        verify(compareService).diffItem(recheckId, diffId, principal.id(), false);
    }

    private RvPortUserPrincipal principal() {
        return new RvPortUserPrincipal(UUID.randomUUID(), "user", "User", "user@example.com",
                false, false, UserStatus.ACTIVE);
    }
}
