#!/bin/sh
set -eu

VERSION="${CODEX_SWITCHER_VERSION:-v0.3.3}"
SCRIPT_URL="https://raw.githubusercontent.com/RomaCredit/codex-provider-switcher/${VERSION}/codex_provider_switcher.py"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10 or newer is required. Install python3 and run this installer again." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
  echo "curl or wget is required." >&2
  exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
  echo "Python 3.10 or newer is required." >&2
  exit 1
fi

if [ -n "${CODEX_SWITCHER_BIN_DIR:-}" ]; then
  bin_dir="$CODEX_SWITCHER_BIN_DIR"
elif [ "$(id -u)" -eq 0 ]; then
  bin_dir="/usr/local/bin"
else
  bin_dir="${HOME}/.local/bin"
fi

if [ -n "${CODEX_SWITCHER_DATA_DIR:-}" ]; then
  data_dir="$CODEX_SWITCHER_DATA_DIR"
elif [ "$(id -u)" -eq 0 ]; then
  data_dir="/usr/local/lib/codex-provider-switcher"
else
  data_dir="${HOME}/.local/share/codex-provider-switcher"
fi

mkdir -p "$bin_dir" "$data_dir"
bin_dir=$(cd "$bin_dir" && pwd)
data_dir=$(cd "$data_dir" && pwd)
program="$data_dir/codex_provider_switcher.py"
for target in "$program" "$bin_dir/cps" "$bin_dir/codex-provider-switcher"; do
  if [ -d "$target" ]; then
    echo "Cannot replace a directory: $target" >&2
    exit 1
  fi
done

temporary=$(mktemp "${program}.tmp.XXXXXX")
launcher_temporary=""
trap 'rm -f "$temporary" "${temporary}.clean" "$launcher_temporary"' EXIT
trap 'exit 1' HUP INT TERM

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$SCRIPT_URL" -o "$temporary"
else
  wget -qO "$temporary" "$SCRIPT_URL"
fi

# A UTF-8 BOM before #! prevents Unix from recognizing the Python shebang.
if [ "$(LC_ALL=C head -c 3 "$temporary")" = "$(printf '\357\273\277')" ]; then
  tail -c +4 "$temporary" > "${temporary}.clean"
  mv "${temporary}.clean" "$temporary"
fi

if ! python3 - "$temporary" "${VERSION#v}" <<'PY'
import ast
import pathlib
import sys

path, expected = sys.argv[1:]
try:
    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8-sig"))
except (OSError, SyntaxError, UnicodeError) as exc:
    raise SystemExit(f"Downloaded program is not valid Python: {exc}")

actual = None
for node in tree.body:
    if not isinstance(node, ast.Assign):
        continue
    if any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            actual = node.value.value
        break
if actual != expected:
    raise SystemExit(f"Downloaded program version mismatch: expected {expected}, got {actual or 'unknown'}")
PY
then
  echo "The requested release could not be installed. Existing installation was not changed." >&2
  exit 1
fi

chmod 755 "$temporary"
mv "$temporary" "$program"

shell_quote() {
  # Quote a path for a later POSIX shell invocation, including spaces and '$'.
  value=$(printf "%s" "$1" | sed "s/'/'\\\\''/g")
  printf "'%s'" "$value"
}

for command_name in codex-provider-switcher cps; do
  launcher="$bin_dir/$command_name"
  launcher_temporary=$(mktemp "${launcher}.tmp.XXXXXX")
  quoted_program=$(shell_quote "$program")
  {
    printf '%s\n' '#!/bin/sh'
    printf 'exec python3 %s "$@"\n' "$quoted_program"
  } > "$launcher_temporary"
  chmod 755 "$launcher_temporary"
  mv "$launcher_temporary" "$launcher"
done
trap - EXIT HUP INT TERM

echo "Installed: $bin_dir/cps"
echo "Installed: $bin_dir/codex-provider-switcher"
case ":${PATH}:" in
  *":${bin_dir}:"*) echo "Run: cps --version" ;;
  *)
    echo "Add $bin_dir to PATH, then run: cps --version"
    printf 'For the current shell: export PATH=%s:"$PATH"\n' "$(shell_quote "$bin_dir")"
    ;;
esac
