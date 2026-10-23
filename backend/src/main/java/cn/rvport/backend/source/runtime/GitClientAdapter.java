package cn.rvport.backend.source.runtime;

public interface GitClientAdapter {

    GitSyncResult sync(GitSyncCommand command);
}
