package cn.rvport.backend.environment.runtime;

public interface SshClientAdapter {

    SshCommandResult execute(SshCommandRequest request);

    SshFileTransferResult upload(SshFileTransferRequest request);

    SshFileTransferResult download(SshFileTransferRequest request);
}
