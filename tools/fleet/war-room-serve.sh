#!/bin/bash
# tools/fleet/war-room-serve.sh -- pull-not-push server for "The war-room"
# (docs/harness.md, "Standing Roles"; issue #279): every GET regenerates the
# page by invoking war-room.sh from this script's own directory, then serves
# the fresh index.html with Cache-Control: no-store. Binds 127.0.0.1 ONLY;
# port 7274 by default, first argument overrides. Ctrl-C stops it cleanly.
# Failure discipline: a nonzero generator exit is logged to this server's
# stderr but the page (which carries its own FAILED banners) is still served.

set -euo pipefail

PORT="${1:-7274}"
case "$PORT" in
  ''|*[!0-9]*)
    echo "war-room-serve.sh: port must be a number, got: $PORT" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GENERATOR="$SCRIPT_DIR/war-room.sh"
# Same path as war-room.sh's default output; passed explicitly with -o so the
# write path and the serve path can never drift apart.
PAGE="/Users/benh/Projects/cardlang-fleet/war-room/index.html"

if [ ! -f "$GENERATOR" ]; then
  echo "war-room-serve.sh: generator not found: $GENERATOR" >&2
  exit 1
fi

# Python stdlib only (http.server); the server is the whole remaining script.
exec /usr/bin/env python3 - "$PORT" "$GENERATOR" "$PAGE" <<'PYEOF'
import http.server
import signal
import subprocess
import sys

# Ctrl-C must stop the server cleanly even when a parent started this process
# with SIGINT ignored (e.g. backgrounded from a non-interactive shell, where
# Python would otherwise skip installing its KeyboardInterrupt handler).
signal.signal(signal.SIGINT, signal.default_int_handler)

port = int(sys.argv[1])
generator = sys.argv[2]
page = sys.argv[3]


class WarRoomHandler(http.server.BaseHTTPRequestHandler):
    server_version = "war-room-serve/1"

    def do_GET(self):
        # Static 404 for favicon probes so one browser visit does not run the
        # generator twice; every other GET regenerates.
        if self.path == "/favicon.ico":
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        # Pull, not push: regenerate on every request. The generator's stdout
        # and stderr are inherited (no pipes), so its progress lands on this
        # server's stderr and no background writer can ever hang a pipe read.
        result = subprocess.run(["/bin/bash", generator, "-o", page])
        if result.returncode != 0:
            print(
                "war-room-serve: generator exited %d (serving the page anyway;"
                " it carries its own FAILED banners)" % result.returncode,
                file=sys.stderr,
                flush=True,
            )
        try:
            with open(page, "rb") as fh:
                body = fh.read()
            status = 200
            ctype = "text/html; charset=utf-8"
        except OSError as exc:
            body = ("war-room-serve: page unreadable: %s\n" % exc).encode("utf-8")
            status = 500
            ctype = "text/plain; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


httpd = http.server.HTTPServer(("127.0.0.1", port), WarRoomHandler)
print("http://127.0.0.1:%d" % port, flush=True)
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("war-room-serve: stopped", file=sys.stderr, flush=True)
finally:
    httpd.server_close()
PYEOF
