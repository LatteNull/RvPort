package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class TaskLogTailReaderTests {

    @TempDir
    private Path tempDir;

    @Test
    void readsLatestDisplayPageFromFileTailInChronologicalOrder() throws Exception {
        Path file = tempDir.resolve("task.log");
        Files.writeString(file, "older-1\nolder-2\nlatest-1\nlatest-2\n");

        TaskLogTailReader.TailResult result = TaskLogTailReader.read(file, 0, 2);

        assertThat(result.content()).isEqualTo("latest-1\nlatest-2");
        assertThat(result.returnedLines()).isEqualTo(2);
        assertThat(result.hasMore()).isTrue();
    }

    @Test
    void readsOlderDisplayPageByOffset() throws Exception {
        Path file = tempDir.resolve("task.log");
        Files.writeString(file, "older-1\nolder-2\nlatest-1\nlatest-2\n");

        TaskLogTailReader.TailResult result = TaskLogTailReader.read(file, 2, 2);

        assertThat(result.content()).isEqualTo("older-1\nolder-2");
        assertThat(result.returnedLines()).isEqualTo(2);
        assertThat(result.hasMore()).isFalse();
    }

    @Test
    void supportsNoTrailingLineBreakAndWindowsLineBreaks() throws Exception {
        Path file = tempDir.resolve("task.log");
        Files.writeString(file, "one\r\ntwo\r\nthree");

        TaskLogTailReader.TailResult result = TaskLogTailReader.read(file, 0, 2);

        assertThat(result.content()).isEqualTo("two\nthree");
        assertThat(result.hasMore()).isTrue();
    }

    @Test
    void handlesEmptyFileMissingFileAndZeroLines() throws Exception {
        Path empty = tempDir.resolve("empty.log");
        Files.writeString(empty, "");

        assertThat(TaskLogTailReader.read(empty, 0, 100).content()).isEmpty();
        assertThat(TaskLogTailReader.read(tempDir.resolve("missing.log"), 0, 100).content()).isEmpty();
        assertThat(TaskLogTailReader.read(empty, 0, 0).content()).isEmpty();
    }

    @Test
    void handlesOffsetBeyondTop() throws Exception {
        Path file = tempDir.resolve("task.log");
        Files.writeString(file, "one\ntwo\n");

        TaskLogTailReader.TailResult result = TaskLogTailReader.read(file, 10, 5);

        assertThat(result.content()).isEmpty();
        assertThat(result.returnedLines()).isZero();
        assertThat(result.hasMore()).isFalse();
    }

    @Test
    void handlesLongSingleLine() throws Exception {
        Path file = tempDir.resolve("task.log");
        String line = "x".repeat(20_000);
        Files.writeString(file, line);

        TaskLogTailReader.TailResult result = TaskLogTailReader.read(file, 0, 1);

        assertThat(result.content()).isEqualTo(line);
        assertThat(result.returnedLines()).isEqualTo(1);
        assertThat(result.hasMore()).isFalse();
    }

    @Test
    void readsLargeLogTailWindowWithoutReturningWholeFile() throws Exception {
        Path file = tempDir.resolve("task.log");
        StringBuilder builder = new StringBuilder();
        for (int index = 1; index <= 10_000; index++) {
            builder.append("line-").append(index).append('\n');
        }
        Files.writeString(file, builder.toString());

        TaskLogTailReader.TailResult result = TaskLogTailReader.read(file, 0, 3);

        assertThat(result.content()).isEqualTo("line-9998\nline-9999\nline-10000");
        assertThat(result.returnedLines()).isEqualTo(3);
        assertThat(result.hasMore()).isTrue();
    }

    @Test
    void readsPartialOlderPageWithoutDuplicates() throws Exception {
        Path file = tempDir.resolve("task.log");
        Files.writeString(file, "one\ntwo\nthree\nfour\nfive");

        TaskLogTailReader.TailResult result = TaskLogTailReader.read(file, 2, 2);

        assertThat(result.content()).isEqualTo("two\nthree");
        assertThat(result.returnedLines()).isEqualTo(2);
        assertThat(result.hasMore()).isTrue();
    }

    @Test
    void preservesUtf8AndEmptyLogicalLines() throws Exception {
        Path file = tempDir.resolve("task.log");
        Files.writeString(file, "开始\n\n完成\n");

        TaskLogTailReader.TailResult result = TaskLogTailReader.read(file, 0, 3);

        assertThat(result.content()).isEqualTo("开始\n\n完成");
        assertThat(result.returnedLines()).isEqualTo(3);
        assertThat(result.hasMore()).isFalse();
    }

    @Test
    void countsLogicalLinesAcrossSupportedSeparators() throws Exception {
        Path file = tempDir.resolve("task.log");
        Files.writeString(file, "one\r\ntwo\rthree\n四");

        assertThat(TaskLogTailReader.countLines(file)).isEqualTo(4);
        assertThat(TaskLogTailReader.countLines("one\r\ntwo\rthree\n四")).isEqualTo(4);
    }

    @Test
    void countsEmptyMissingAndTrailingSeparators() throws Exception {
        Path empty = tempDir.resolve("empty.log");
        Files.writeString(empty, "");

        assertThat(TaskLogTailReader.countLines((CharSequence) null)).isZero();
        assertThat(TaskLogTailReader.countLines("")).isZero();
        assertThat(TaskLogTailReader.countLines("one\n")).isEqualTo(1);
        assertThat(TaskLogTailReader.countLines("one\r")).isEqualTo(1);
        assertThat(TaskLogTailReader.countLines(empty)).isZero();
        assertThat(TaskLogTailReader.countLines(tempDir.resolve("missing.log"))).isZero();
    }

    @Test
    void supportsStandaloneCarriageReturnsAndDelimiterAcrossSearchBufferBoundary() throws Exception {
        Path carriageReturn = tempDir.resolve("cr.log");
        Files.writeString(carriageReturn, "one\rtwo\rthree\r");
        assertThat(TaskLogTailReader.read(carriageReturn, 0, 3).content()).isEqualTo("one\ntwo\nthree");

        Path boundary = tempDir.resolve("boundary.log");
        String first = "x".repeat(8191);
        Files.writeString(boundary, first + "\r\nlast");
        TaskLogTailReader.TailResult result = TaskLogTailReader.read(boundary, 0, 2);
        assertThat(result.content()).isEqualTo(first + "\nlast");
        assertThat(result.hasMore()).isFalse();
    }
}
