"""源码包含查询索引；保持原 Evidence 顺序及闭区间包含语义。"""
from bisect import bisect_right
from collections import defaultdict


class SpanLookup:
    def __init__(self, values):
        groups = defaultdict(list)
        for ordinal, item in enumerate(values):
            if item.location is None:
                continue
            span = item.location
            groups[item.subject_id, span.start.path].append((
                (span.start.line, span.start.column or 1),
                (span.end.line, span.end.column or 1), ordinal, item))
        self.groups = {}
        for key, rows in groups.items():
            rows.sort(key=lambda row: (row[0], row[2]))
            maximum, ends = (0, 0), []
            for row in rows:
                maximum = max(maximum, row[1])
                ends.append(maximum)
            self.groups[key] = rows, [row[0] for row in rows], ends

    def containing(self, item):
        if item.location is None:
            return ()
        span = item.location
        rows, starts, ends = self.groups.get((item.subject_id, span.start.path), ((), (), ()))
        end = span.end.line, span.end.column or 1
        position = bisect_right(starts, (span.start.line, span.start.column or 1)) - 1
        result = []
        while position >= 0 and ends[position] >= end:
            row = rows[position]
            if row[1] >= end:
                result.append((row[2], row[3]))
            position -= 1
        return tuple(value for _, value in sorted(result))
