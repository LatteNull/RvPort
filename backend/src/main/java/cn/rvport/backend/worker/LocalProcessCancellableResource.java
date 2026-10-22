package cn.rvport.backend.worker;

import java.time.Duration;
import java.util.Comparator;
import java.util.concurrent.TimeUnit;

public class LocalProcessCancellableResource implements CancellableResource {

    private final Process process;
    private final Duration gracePeriod;

    public LocalProcessCancellableResource(Process process, Duration gracePeriod) {
        this.process = process;
        this.gracePeriod = gracePeriod == null ? Duration.ofSeconds(5) : gracePeriod;
    }

    @Override
    public void cancel() {
        ProcessHandle handle = process.toHandle();
        handle.descendants()
                .sorted(Comparator.comparingLong(ProcessHandle::pid).reversed())
                .forEach(ProcessHandle::destroy);
        handle.destroy();
        try {
            process.waitFor(gracePeriod.toMillis(), TimeUnit.MILLISECONDS);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
        }
        if (handle.isAlive()) {
            handle.descendants()
                    .sorted(Comparator.comparingLong(ProcessHandle::pid).reversed())
                    .forEach(ProcessHandle::destroyForcibly);
            handle.destroyForcibly();
        }
    }
}
