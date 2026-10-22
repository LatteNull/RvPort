package cn.rvport.backend.task;

import cn.rvport.backend.common.error.ApiException;
import java.io.BufferedReader;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayDeque;
import java.util.Deque;
import org.springframework.http.HttpStatus;

final class TaskLogTailReader {

    private static final int SEARCH_BUFFER_SIZE = 8192;

    private TaskLogTailReader() {
    }

    static TailResult read(Path path, long offset, int lines) {
        if (lines == 0 || !Files.isRegularFile(path)) {
            return TailResult.empty();
        }
        try (FileChannel channel = FileChannel.open(path, StandardOpenOption.READ)) {
            ReverseLineCursor cursor = ReverseLineCursor.open(channel);
            for (long skipped = 0; skipped < offset; skipped++) {
                if (cursor.previous(false) == null) {
                    return TailResult.empty();
                }
            }
            Deque<String> selected = new ArrayDeque<>();
            int returnedLines = 0;
            for (; returnedLines < lines; returnedLines++) {
                String line = cursor.previous(true);
                if (line == null) {
                    break;
                }
                selected.addFirst(line);
            }
            return new TailResult(String.join("\n", selected), returnedLines, cursor.hasPrevious());
        } catch (IOException ex) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "TASK_LOG_READ_FAILED", "任务日志读取失败");
        }
    }

    private static final class ReverseLineCursor {

        private final FileChannel channel;
        private long endExclusive;
        private boolean hasPrevious;

        private ReverseLineCursor(FileChannel channel, long endExclusive, boolean hasPrevious) {
            this.channel = channel;
            this.endExclusive = endExclusive;
            this.hasPrevious = hasPrevious;
        }

        static ReverseLineCursor open(FileChannel channel) throws IOException {
            long size = channel.size();
            if (size == 0) {
                return new ReverseLineCursor(channel, 0, false);
            }
            long endExclusive = size;
            byte last = readByte(channel, size - 1);
            if (last == '\n') {
                endExclusive--;
                if (endExclusive > 0 && readByte(channel, endExclusive - 1) == '\r') {
                    endExclusive--;
                }
            } else if (last == '\r') {
                endExclusive--;
            }
            return new ReverseLineCursor(channel, endExclusive, true);
        }

        String previous(boolean includeContent) throws IOException {
            if (!hasPrevious) {
                return null;
            }
            Separator separator = findPreviousSeparator(channel, endExclusive);
            long start = separator == null ? 0 : separator.endExclusive();
            String content = includeContent ? readUtf8(channel, start, endExclusive) : "";
            if (separator == null) {
                endExclusive = 0;
                hasPrevious = false;
            } else {
                endExclusive = separator.start();
            }
            return content;
        }

        boolean hasPrevious() {
            return hasPrevious;
        }
    }

    private static Separator findPreviousSeparator(FileChannel channel, long beforeExclusive) throws IOException {
        long searchEnd = beforeExclusive;
        while (searchEnd > 0) {
            long searchStart = Math.max(0, searchEnd - SEARCH_BUFFER_SIZE);
            int length = Math.toIntExact(searchEnd - searchStart);
            ByteBuffer buffer = ByteBuffer.allocate(length);
            readFully(channel, buffer, searchStart);
            byte[] bytes = buffer.array();
            for (int index = length - 1; index >= 0; index--) {
                byte current = bytes[index];
                long absoluteIndex = searchStart + index;
                if (current == '\n') {
                    long delimiterStart = absoluteIndex;
                    if (index > 0 ? bytes[index - 1] == '\r'
                            : absoluteIndex > 0 && readByte(channel, absoluteIndex - 1) == '\r') {
                        delimiterStart--;
                    }
                    return new Separator(delimiterStart, absoluteIndex + 1);
                }
                if (current == '\r') {
                    return new Separator(absoluteIndex, absoluteIndex + 1);
                }
            }
            searchEnd = searchStart;
        }
        return null;
    }

    private static String readUtf8(FileChannel channel, long start, long endExclusive) throws IOException {
        int length = Math.toIntExact(endExclusive - start);
        if (length == 0) {
            return "";
        }
        ByteBuffer buffer = ByteBuffer.allocate(length);
        readFully(channel, buffer, start);
        return new String(buffer.array(), StandardCharsets.UTF_8);
    }

    private static byte readByte(FileChannel channel, long position) throws IOException {
        ByteBuffer buffer = ByteBuffer.allocate(1);
        readFully(channel, buffer, position);
        return buffer.array()[0];
    }

    private static void readFully(FileChannel channel, ByteBuffer buffer, long position) throws IOException {
        while (buffer.hasRemaining()) {
            int read = channel.read(buffer, position);
            if (read < 0) {
                throw new IOException("Unexpected end of task log");
            }
            position += read;
        }
    }

    private record Separator(long start, long endExclusive) {
    }

    static long countLines(Path path) {
        if (!Files.isRegularFile(path)) {
            return 0;
        }
        try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            long total = 0;
            while (reader.readLine() != null) {
                total++;
            }
            return total;
        } catch (IOException ex) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "TASK_LOG_READ_FAILED", "任务日志读取失败");
        }
    }

    static long countLines(CharSequence content) {
        if (content == null || content.isEmpty()) {
            return 0;
        }
        long total = 0;
        for (int index = 0; index < content.length(); index++) {
            char current = content.charAt(index);
            if (current == '\n') {
                total++;
            } else if (current == '\r') {
                total++;
                if (index + 1 < content.length() && content.charAt(index + 1) == '\n') {
                    index++;
                }
            }
        }
        char last = content.charAt(content.length() - 1);
        if (last != '\n' && last != '\r') {
            total++;
        }
        return total;
    }

    record TailResult(
            String content,
            int returnedLines,
            boolean hasMore
    ) {
        static TailResult empty() {
            return new TailResult("", 0, false);
        }
    }
}
