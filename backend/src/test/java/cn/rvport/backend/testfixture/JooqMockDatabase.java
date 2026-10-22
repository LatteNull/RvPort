package cn.rvport.backend.testfixture;

import java.sql.SQLException;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Deque;
import java.util.List;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.Record;
import org.jooq.Result;
import org.jooq.SQLDialect;
import org.jooq.impl.DSL;
import org.jooq.tools.jdbc.MockConnection;
import org.jooq.tools.jdbc.MockDataProvider;
import org.jooq.tools.jdbc.MockExecuteContext;
import org.jooq.tools.jdbc.MockResult;

public final class JooqMockDatabase implements MockDataProvider, AutoCloseable {

    private final MockConnection connection = new MockConnection(this);
    private final DSLContext dsl = DSL.using(connection, SQLDialect.POSTGRES);
    private final Deque<MockResult[]> responses = new ArrayDeque<>();
    private final List<Execution> executions = new ArrayList<>();

    public DSLContext dsl() {
        return dsl;
    }

    public List<Execution> executions() {
        return List.copyOf(executions);
    }

    public Execution lastExecution() {
        if (executions.isEmpty()) {
            throw new IllegalStateException("尚未执行 SQL");
        }
        return executions.getLast();
    }

    public JooqMockDatabase enqueueRows(int rows) {
        return enqueue(new MockResult(rows));
    }

    public JooqMockDatabase enqueueResult(Result<?> result) {
        return enqueue(new MockResult(result.size(), result));
    }

    public JooqMockDatabase enqueueRecord(Record record) {
        return enqueue(new MockResult(record));
    }

    public JooqMockDatabase enqueueFailure(SQLException exception) {
        return enqueue(new MockResult(exception));
    }

    public JooqMockDatabase enqueue(MockResult... results) {
        responses.addLast(results.clone());
        return this;
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    public Result<Record> result(Field<?>[] fields, Object[]... rows) {
        Result<Record> result = dsl.newResult(fields);
        for (Object[] values : rows) {
            if (values.length != fields.length) {
                throw new IllegalArgumentException("字段数量与值数量不一致");
            }
            Record record = dsl.newRecord(fields);
            for (int index = 0; index < fields.length; index++) {
                record.set((Field) fields[index], values[index]);
            }
            result.add(record);
        }
        return result;
    }

    @Override
    public MockResult[] execute(MockExecuteContext context) throws SQLException {
        executions.add(new Execution(
                context.sql(),
                copy(context.bindings()),
                List.copyOf(Arrays.asList(context.batchSQL().clone())),
                copy(context.batchBindings()),
                context.batch(),
                context.batchSingle(),
                context.batchMultiple()
        ));
        if (responses.isEmpty()) {
            throw new SQLException("测试未配置 SQL 响应: " + context.sql());
        }
        return responses.removeFirst();
    }

    public void verifyComplete() {
        if (!responses.isEmpty()) {
            throw new AssertionError("仍有 " + responses.size() + " 个未消费的 SQL 响应");
        }
    }

    @Override
    public void close() throws SQLException {
        connection.close();
    }

    private static Object[] copy(Object[] values) {
        return values == null ? new Object[0] : values.clone();
    }

    private static List<Object[]> copy(Object[][] values) {
        if (values == null) {
            return List.of();
        }
        return Arrays.stream(values).map(JooqMockDatabase::copy).toList();
    }

    public record Execution(
            String sql,
            Object[] bindings,
            List<String> batchSql,
            List<Object[]> batchBindings,
            boolean batch,
            boolean batchSingle,
            boolean batchMultiple
    ) {
        public Execution {
            bindings = bindings.clone();
            batchSql = List.copyOf(batchSql);
            batchBindings = batchBindings.stream().map(Object[]::clone).toList();
        }

        @Override
        public Object[] bindings() {
            return bindings.clone();
        }

        @Override
        public List<Object[]> batchBindings() {
            return batchBindings.stream().map(Object[]::clone).toList();
        }

        public String normalizedSql() {
            return sql.replace("\"public\".", "").replace("\"", "");
        }
    }
}
