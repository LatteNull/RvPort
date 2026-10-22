package cn.rvport.backend.dependency.autofix;

import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

@Component
public class DependencyPackageInstallPlanner {

    private static final Pattern PACKAGE_NAME = Pattern.compile("^[A-Za-z0-9._+:-]+$");
    private static final Pattern VERSION = Pattern.compile("^[A-Za-z0-9._+~:-]+$");

    public void validatePackageName(String value) {
        if (value == null || value.isBlank() || !PACKAGE_NAME.matcher(value).matches()) {
            throw new IllegalArgumentException("软件包名称不安全或为空");
        }
    }

    public void validateVersionConstraint(String value) {
        if (value != null && !value.isBlank() && !VERSION.matcher(value).matches()) {
            throw new IllegalArgumentException("软件包版本约束不安全");
        }
    }

    public String rpmInstallScript(DependencyAutoFixItemView item) {
        validatePackageName(item.installPackageName());
        validateVersionConstraint(item.installVersionConstraint());
        String pkg = shellQuote(item.installPackageName());
        String version = shellQuote(item.installVersionConstraint() == null ? "" : item.installVersionConstraint());
        String major = shellQuote(item.riskLevel().name().equals("HIGH") && item.installVersionConstraint() != null
                ? item.installVersionConstraint()
                : "");
        return """
                set -u
                pkg=%s
                version_constraint=%s
                major_constraint=%s
                pm=''
                if command -v dnf >/dev/null 2>&1; then pm='dnf'; elif command -v yum >/dev/null 2>&1; then pm='yum'; else echo 'RVPORT_AUTO_FIX_UNSUPPORTED_PACKAGE_MANAGER'; exit 12; fi
                echo "RVPORT_AUTO_FIX_PACKAGE_MANAGER=$pm"
                if rpm -q "$pkg" >/tmp/rvport-autofix-installed.$$ 2>/tmp/rvport-autofix-installed-err.$$; then
                  cat /tmp/rvport-autofix-installed.$$ || true
                  rm -f /tmp/rvport-autofix-installed.$$ /tmp/rvport-autofix-installed-err.$$
                  echo 'RVPORT_AUTO_FIX_ALREADY_SATISFIED'
                  exit 10
                fi
                rm -f /tmp/rvport-autofix-installed.$$ /tmp/rvport-autofix-installed-err.$$
                query_cmd="$pm --setopt=timeout=10 --setopt=retries=0 --setopt=skip_if_unavailable=True repoquery --available --qf '%%{name}|%%{version}-%%{release}|%%{arch}'"
                if ! sh -c "$query_cmd '$pkg'" > /tmp/rvport-autofix-candidates.$$ 2>/tmp/rvport-autofix-query-err.$$; then
                  echo 'RVPORT_AUTO_FIX_QUERY_FAILED'
                  cat /tmp/rvport-autofix-query-err.$$ || true
                  rm -f /tmp/rvport-autofix-candidates.$$ /tmp/rvport-autofix-query-err.$$
                  exit 13
                fi
                cat /tmp/rvport-autofix-candidates.$$ | head -20
                if [ ! -s /tmp/rvport-autofix-candidates.$$ ]; then
                  echo 'RVPORT_AUTO_FIX_PACKAGE_UNAVAILABLE'
                  rm -f /tmp/rvport-autofix-candidates.$$ /tmp/rvport-autofix-query-err.$$
                  exit 11
                fi
                install_spec="$pkg"
                if [ -n "$major_constraint" ]; then
                  if ! awk -F'|' -v major="$major_constraint" '$2 ~ "^" major { found=1 } END { exit found ? 0 : 1 }' /tmp/rvport-autofix-candidates.$$; then
                    echo 'RVPORT_AUTO_FIX_MAJOR_UNAVAILABLE'
                    rm -f /tmp/rvport-autofix-candidates.$$ /tmp/rvport-autofix-query-err.$$
                    exit 11
                  fi
                elif [ -n "$version_constraint" ]; then
                  install_spec="$pkg-$version_constraint"
                fi
                echo "RVPORT_AUTO_FIX_INSTALL=$install_spec"
                if "$pm" -y install "$install_spec"; then
                  rm -f /tmp/rvport-autofix-candidates.$$ /tmp/rvport-autofix-query-err.$$
                  echo 'RVPORT_AUTO_FIX_INSTALLED'
                  exit 0
                fi
                if [ "$install_spec" != "$pkg" ]; then
                  echo "RVPORT_AUTO_FIX_INSTALL_FALLBACK=$pkg"
                  if "$pm" -y install "$pkg"; then
                    rm -f /tmp/rvport-autofix-candidates.$$ /tmp/rvport-autofix-query-err.$$
                    echo 'RVPORT_AUTO_FIX_INSTALLED_FALLBACK'
                    exit 0
                  fi
                fi
                rm -f /tmp/rvport-autofix-candidates.$$ /tmp/rvport-autofix-query-err.$$
                echo 'RVPORT_AUTO_FIX_INSTALL_FAILED'
                exit 14
                """.formatted(pkg, version, major);
    }

    private String shellQuote(String value) {
        if (value == null || value.isBlank()) {
            return "''";
        }
        return "'" + value.replace("'", "'\"'\"'") + "'";
    }
}
