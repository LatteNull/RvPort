package cn.rvport.backend.archive;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpStatus;
import org.springframework.mock.web.MockHttpServletRequest;

class ProjectArchiveControllerTests {

    private final ProjectArchiveService service = mock(ProjectArchiveService.class);
    private final ProjectArchiveController controller = new ProjectArchiveController(service);
    private final RvPortUserPrincipal principal = new RvPortUserPrincipal(UUID.randomUUID(), "admin", "Admin",
            "admin@example.com", true, false, UserStatus.ACTIVE);
    private final MockHttpServletRequest request = new MockHttpServletRequest();

    @Test
    void delegatesCreateOverviewLatestListAndGet() {
        UUID projectId = UUID.randomUUID();
        UUID archiveId = UUID.randomUUID();

        assertThat(controller.create(principal, projectId, request).timestamp()).isNotNull();
        assertThat(controller.overview(principal, projectId, request).timestamp()).isNotNull();
        assertThat(controller.latest(principal, projectId, request).timestamp()).isNotNull();
        assertThat(controller.list(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.get(principal, archiveId, request).timestamp()).isNotNull();

        verify(service).createCurrent(projectId, principal.id(), true);
        verify(service).overview(projectId, principal.id(), true);
        verify(service).latest(projectId, principal.id(), true);
        verify(service).list(projectId, null, principal.id(), true);
        verify(service).get(archiveId, principal.id(), true);
    }

    @Test
    void itemAndArchiveDownloadsUseSafeAttachmentMetadata() {
        UUID archiveId = UUID.randomUUID();
        UUID itemId = UUID.randomUUID();
        ByteArrayResource itemResource = new ByteArrayResource("item".getBytes());
        ByteArrayResource zipResource = new ByteArrayResource("zip".getBytes());
        when(service.downloadItem(archiveId, itemId, "html", principal.id(), true))
                .thenReturn(new ProjectArchiveDownload(itemResource, "item.html", "text/html"));
        when(service.download(archiveId, principal.id(), true))
                .thenReturn(new ProjectArchiveDownload(zipResource, "archive.zip", "application/zip"));

        var item = controller.item(principal, archiveId, itemId, "html");
        var archive = controller.download(principal, archiveId);

        assertThat(item.getBody()).isSameAs(itemResource);
        assertThat(item.getHeaders().getContentDisposition().getFilename()).isEqualTo("item.html");
        assertThat(archive.getBody()).isSameAs(zipResource);
        assertThat(archive.getHeaders().getContentType().toString()).isEqualTo("application/zip");
    }

    @Test
    void serviceErrorsPropagateWithoutBeingRewritten() {
        UUID archiveId = UUID.randomUUID();
        ApiException failure = new ApiException(HttpStatus.NOT_FOUND, "ARCHIVE_NOT_FOUND", "归档不存在");
        when(service.get(archiveId, principal.id(), true)).thenThrow(failure);

        assertThatThrownBy(() -> controller.get(principal, archiveId, request)).isSameAs(failure);
    }
}
