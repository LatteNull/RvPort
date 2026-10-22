package cn.rvport.backend.buildvalidation;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Pattern;

public final class CMakeCompilerFlagProbeParser {

    private CMakeCompilerFlagProbeParser() {
    }

    public static List<Probe> parse(String relativePath, String content) {
        String text = content == null ? "" : content;
        List<Probe> probes = new ArrayList<>();
        int index = 0;
        while (index < text.length()) {
            if (text.charAt(index) == '#') {
                while (index < text.length() && text.charAt(index) != '\n') {
                    index++;
                }
                continue;
            }
            if (!isIdentifierStart(text.charAt(index))) {
                index++;
                continue;
            }
            int nameStart = index;
            index++;
            while (index < text.length() && isIdentifierPart(text.charAt(index))) {
                index++;
            }
            String function = text.substring(nameStart, index);
            String normalizedFunction = function.toLowerCase(Locale.ROOT);
            if (!isSupportedFunction(normalizedFunction)) {
                continue;
            }
            int cursor = skipWhitespaceAndComments(text, index);
            if (cursor >= text.length() || text.charAt(cursor) != '(') {
                continue;
            }
            Block block = readBlock(text, cursor);
            if (block == null) {
                probes.add(Probe.unresolved("", "", relativePath, normalizedFunction, "unbalanced_parentheses"));
                break;
            }
            List<String> args = splitArguments(block.content());
            probes.add(toProbe(relativePath, normalizedFunction, args));
            index = block.endIndex();
        }
        probes.addAll(parseForeachExpansions(relativePath, text));
        return probes;
    }

    private static List<Probe> parseForeachExpansions(String relativePath, String text) {
        Map<String, List<String>> lists = cmakeLists(text);
        List<Probe> probes = new ArrayList<>();
        int index = 0;
        while (index < text.length()) {
            int foreachIndex = indexOfIgnoreCase(text, "foreach", index);
            if (foreachIndex < 0) {
                break;
            }
            int open = skipWhitespaceAndComments(text, foreachIndex + "foreach".length());
            if (open >= text.length() || text.charAt(open) != '(') {
                index = foreachIndex + "foreach".length();
                continue;
            }
            Block header = readBlock(text, open);
            if (header == null) {
                break;
            }
            int end = indexOfIgnoreCase(text, "endforeach", header.endIndex());
            if (end < 0) {
                break;
            }
            List<String> args = splitArguments(header.content());
            if (args.size() < 2) {
                index = end + "endforeach".length();
                continue;
            }
            String loopVariable = args.get(0);
            List<String> loopValues = new ArrayList<>();
            for (String arg : args.subList(1, args.size())) {
                if (isVariableRef(arg)) {
                    loopValues.addAll(lists.getOrDefault(variableRefName(arg), List.of()));
                } else {
                    loopValues.add(arg);
                }
            }
            if (loopValues.isEmpty()) {
                index = end + "endforeach".length();
                continue;
            }
            String body = text.substring(header.endIndex(), end);
            probes.addAll(expandForeachBody(relativePath, body, loopVariable, loopValues));
            index = end + "endforeach".length();
        }
        return probes;
    }

    private static Map<String, List<String>> cmakeLists(String text) {
        Map<String, List<String>> lists = new LinkedHashMap<>();
        for (Call call : calls(text)) {
            if ("list".equals(call.function())) {
                List<String> args = splitArguments(call.content());
                if (args.size() >= 3 && "append".equals(args.get(0).toLowerCase(Locale.ROOT))) {
                    lists.computeIfAbsent(args.get(1), ignored -> new ArrayList<>()).addAll(args.subList(2, args.size()));
                }
            } else if ("set".equals(call.function())) {
                List<String> args = splitArguments(call.content());
                if (args.size() >= 2) {
                    lists.computeIfAbsent(args.get(0), ignored -> new ArrayList<>()).addAll(args.subList(1, args.size()));
                }
            }
        }
        return lists;
    }

    private static List<Probe> expandForeachBody(String relativePath, String body, String loopVariable, List<String> loopValues) {
        List<Probe> probes = new ArrayList<>();
        Map<String, DerivedVariable> derivedVariables = new LinkedHashMap<>();
        for (Call call : calls(body)) {
            if ("string".equals(call.function())) {
                List<String> args = splitArguments(call.content());
                if (args.size() >= 6
                        && "regex".equals(args.get(0).toLowerCase(Locale.ROOT))
                        && "replace".equals(args.get(1).toLowerCase(Locale.ROOT))
                        && isVariableRef(args.get(5))
                        && variableRefName(args.get(5)).equals(loopVariable)) {
                    derivedVariables.put(args.get(4), new DerivedVariable(args.get(2), args.get(3)));
                }
            }
        }
        for (Call call : calls(body)) {
            if (!isSupportedFunction(call.function())) {
                continue;
            }
            List<String> args = splitArguments(call.content());
            for (String loopValue : loopValues) {
                Map<String, String> variables = new LinkedHashMap<>();
                variables.put(loopVariable, loopValue);
                for (Map.Entry<String, DerivedVariable> entry : derivedVariables.entrySet()) {
                    variables.put(entry.getKey(), entry.getValue().apply(loopValue));
                }
                probes.add(toProbe(relativePath, call.function(), substitute(args, variables)));
            }
        }
        return probes;
    }

    private static List<String> substitute(List<String> args, Map<String, String> variables) {
        List<String> values = new ArrayList<>();
        for (String arg : args) {
            String value = arg;
            for (Map.Entry<String, String> entry : variables.entrySet()) {
                value = value.replace("${" + entry.getKey() + "}", entry.getValue());
            }
            values.add(value);
        }
        return values;
    }

    private static List<Call> calls(String text) {
        List<Call> calls = new ArrayList<>();
        int index = 0;
        while (index < text.length()) {
            if (text.charAt(index) == '#') {
                while (index < text.length() && text.charAt(index) != '\n') {
                    index++;
                }
                continue;
            }
            if (!isIdentifierStart(text.charAt(index))) {
                index++;
                continue;
            }
            int start = index;
            index++;
            while (index < text.length() && isIdentifierPart(text.charAt(index))) {
                index++;
            }
            String function = text.substring(start, index).toLowerCase(Locale.ROOT);
            int cursor = skipWhitespaceAndComments(text, index);
            if (cursor >= text.length() || text.charAt(cursor) != '(') {
                continue;
            }
            Block block = readBlock(text, cursor);
            if (block == null) {
                break;
            }
            calls.add(new Call(function, block.content()));
            index = block.endIndex();
        }
        return calls;
    }

    private static Probe toProbe(String relativePath, String function, List<String> args) {
        String language = "";
        String flag = "";
        String variable = "";
        if ("check_c_compiler_flag".equals(function) && args.size() >= 2) {
            language = "C";
            flag = args.get(0);
            variable = args.get(1);
        } else if ("check_cxx_compiler_flag".equals(function) && args.size() >= 2) {
            language = "CXX";
            flag = args.get(0);
            variable = args.get(1);
        } else if ("check_compiler_flag".equals(function) && args.size() >= 3) {
            language = args.get(0);
            flag = args.get(1);
            variable = args.get(2);
        }
        String reason = "";
        if (flag.isBlank() || variable.isBlank()) {
            reason = "insufficient_arguments";
        } else if (flag.contains("${") || variable.contains("${")) {
            reason = "variable_expansion";
        }
        if (!reason.isBlank()) {
            return Probe.unresolved(variable, flag, relativePath, function, reason);
        }
        return new Probe(variable, language, flag, relativePath, function, false, "");
    }

    private static boolean isSupportedFunction(String function) {
        return "check_c_compiler_flag".equals(function)
                || "check_cxx_compiler_flag".equals(function)
                || "check_compiler_flag".equals(function);
    }

    private static boolean isVariableRef(String value) {
        return value != null && value.startsWith("${") && value.endsWith("}");
    }

    private static String variableRefName(String value) {
        return value.substring(2, value.length() - 1);
    }

    private static int indexOfIgnoreCase(String text, String needle, int from) {
        return text.toLowerCase(Locale.ROOT).indexOf(needle.toLowerCase(Locale.ROOT), from);
    }

    private static Block readBlock(String text, int openParenIndex) {
        int depth = 0;
        char quote = 0;
        StringBuilder content = new StringBuilder();
        for (int i = openParenIndex; i < text.length(); i++) {
            char current = text.charAt(i);
            if (quote != 0) {
                if (current == '\\' && i + 1 < text.length()) {
                    content.append(current).append(text.charAt(++i));
                    continue;
                }
                if (current == quote) {
                    quote = 0;
                }
                content.append(current);
                continue;
            }
            if (current == '"' || current == '\'') {
                quote = current;
                content.append(current);
                continue;
            }
            if (current == '#') {
                while (i < text.length() && text.charAt(i) != '\n') {
                    i++;
                }
                content.append(' ');
                continue;
            }
            if (current == '(') {
                depth++;
                if (depth > 1) {
                    content.append(current);
                }
                continue;
            }
            if (current == ')') {
                depth--;
                if (depth == 0) {
                    return new Block(content.toString(), i + 1);
                }
                content.append(current);
                continue;
            }
            content.append(current);
        }
        return null;
    }

    private static List<String> splitArguments(String text) {
        List<String> args = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        char quote = 0;
        boolean tokenStarted = false;
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (quote != 0) {
                if (c == '\\' && i + 1 < text.length()) {
                    current.append(text.charAt(++i));
                    tokenStarted = true;
                    continue;
                }
                if (c == quote) {
                    quote = 0;
                    tokenStarted = true;
                    continue;
                }
                current.append(c);
                tokenStarted = true;
                continue;
            }
            if (c == '"' || c == '\'') {
                quote = c;
                tokenStarted = true;
                continue;
            }
            if (Character.isWhitespace(c)) {
                if (tokenStarted) {
                    args.add(current.toString());
                    current.setLength(0);
                    tokenStarted = false;
                }
                continue;
            }
            current.append(c);
            tokenStarted = true;
        }
        if (tokenStarted) {
            args.add(current.toString());
        }
        return args;
    }

    private static int skipWhitespaceAndComments(String text, int index) {
        int cursor = index;
        while (cursor < text.length()) {
            char c = text.charAt(cursor);
            if (Character.isWhitespace(c)) {
                cursor++;
                continue;
            }
            if (c == '#') {
                while (cursor < text.length() && text.charAt(cursor) != '\n') {
                    cursor++;
                }
                continue;
            }
            break;
        }
        return cursor;
    }

    private static boolean isIdentifierStart(char c) {
        return Character.isLetter(c) || c == '_';
    }

    private static boolean isIdentifierPart(char c) {
        return Character.isLetterOrDigit(c) || c == '_';
    }

    private record Block(String content, int endIndex) {
    }

    private record Call(String function, String content) {
    }

    private record DerivedVariable(String regex, String replacement) {
        String apply(String value) {
            try {
                return Pattern.compile(regex).matcher(value).replaceAll(replacement);
            } catch (RuntimeException ex) {
                return value;
            }
        }
    }

    public record Probe(
            String variable,
            String language,
            String flag,
            String file,
            String function,
            boolean unresolved,
            String unresolvedReason
    ) {
        static Probe unresolved(String variable, String flag, String file, String function, String reason) {
            return new Probe(variable == null ? "" : variable, "", flag == null ? "" : flag,
                    file == null ? "" : file, function == null ? "" : function, true, reason);
        }
    }
}
