package cn.rvport.backend.source;

public record SourceArchiveResponse(
        SourceRevisionResponse sourceRevision,
        SourceImportResponse sourceImport
) {
}
