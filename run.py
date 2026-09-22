"""Run either project independently or both behind one local port.

The two applications intentionally remain separate. In merged mode this
launcher starts each existing FastAPI application on an internal port and
proxies them through one public HTTP port, so their routes and dashboards do
not need to be rewritten or renamed.
"""

from __future__ import annotations

import argparse
import html
import http.client
import os
import re
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
COST_PROJECT = ROOT / "Cloud_Cost_Prediction_And_Optimization"
OPTIMA_PROJECT = ROOT / "CloudOptima-3"

COST_ALIASES = (
    "/cost-optimization",
    "/cloud-cost-prediction-and-optimization",
    "/cloud-cost-prediction",
    "/cost",
)
OPTIMA_ALIASES = (
    "/cloudoptima",
    "/cloud-optima",
    "/optima",
)


def project_python(project: Path) -> str:
    """Use a project's environment when it exists, otherwise the active one."""
    candidate = project / "venv" / "Scripts" / "python.exe"
    return str(candidate) if candidate.exists() else sys.executable


def project_environment(project: Path) -> dict[str, str]:
    environment = os.environ.copy()
    env_file = project / ".env"
    if not env_file.exists() or "DATABASE_URL" in environment:
        return environment

    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("DATABASE_URL="):
            database_url = line.partition("=")[2].strip()
            # `db` is the Compose service name; from Windows Python use the
            # host-mapped PostgreSQL port instead.
            environment["DATABASE_URL"] = re.sub(
                r"(^|://|@)db(?=[:/])",
                r"\g<1>127.0.0.1",
                database_url,
            )
            break
    return environment


def start_project(project: Path, module: str, port: int) -> subprocess.Popen[bytes]:
    command = [
        project_python(project),
        "-m",
        "uvicorn",
        module,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    return subprocess.Popen(command, cwd=project, env=project_environment(project))


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class GatewayHandler(BaseHTTPRequestHandler):
    """Small dependency-free reverse proxy for the two existing applications."""

    protocol_version = "HTTP/1.1"
    routes = {
        "cost": ("127.0.0.1", 8101),
        "optima": ("127.0.0.1", 8102),
    }

    def do_GET(self) -> None:
        self.proxy()

    def do_POST(self) -> None:
        self.proxy()

    def do_PUT(self) -> None:
        self.proxy()

    def do_PATCH(self) -> None:
        self.proxy()

    def do_DELETE(self) -> None:
        self.proxy()

    def proxy(self) -> None:
        target, path = self.target_for(self.path)
        if target is None:
            self.send_error(404, "Unknown merged-project route")
            return

        host, port = self.routes[target]
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in {"host", "content-length", "connection"}
        }
        headers["Host"] = f"{host}:{port}"

        connection = http.client.HTTPConnection(host, port, timeout=120)
        try:
            connection.request(self.command, path, body=body, headers=headers)
            response = connection.getresponse()
            response_body = response.read()
        except (ConnectionError, OSError) as exc:
            self.send_error(503, f"Backend unavailable: {exc}")
            return
        finally:
            connection.close()

        self.send_response(response.status, response.reason)
        for key, value in response.getheaders():
            if key.lower() not in {"transfer-encoding", "connection", "content-length"}:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    @staticmethod
    def target_for(raw_path: str) -> tuple[str | None, str]:
        path = urlsplit(raw_path).path
        query = urlsplit(raw_path).query
        suffix = f"?{query}" if query else ""

        def alias_target(aliases: tuple[str, ...], target: str) -> tuple[str | None, str] | None:
            for alias in aliases:
                if path in {alias, alias + "/"}:
                    return target, "/" + suffix
                if path.startswith(alias + "/"):
                    return target, path[len(alias) :] + suffix
            return None

        project_match = alias_target(COST_ALIASES, "cost")
        if project_match is not None:
            return project_match

        project_match = alias_target(OPTIMA_ALIASES, "optima")
        if project_match is not None:
            return project_match

        if path.startswith("/api/v1/") or path == "/api/v1":
            return "cost", path + suffix
        if path.startswith("/dashboard/") or path == "/dashboard":
            return "cost", path + suffix
        if path.startswith("/api/") or path == "/api":
            return "optima", path + suffix
        if path in {"/docs", "/docs/"}:
            return "cost", path + suffix
        if path in {"/openapi.json", "/openapi.json/"}:
            return "cost", path + suffix
        return None, path + suffix

    def log_message(self, format: str, *args: object) -> None:
        print(f"[gateway] {format % args}")


def landing_page(public_port: int) -> bytes:
    port = html.escape(str(public_port))
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cloud FinOps Suite</title>
<style>
body{{margin:0;background:#eef2f7;color:#172033;font:16px system-ui,sans-serif}}
header{{padding:22px 32px;background:#172033;color:white}}
header h1{{margin:0 0 6px}} header p{{margin:0;color:#cbd5e1}}
main{{display:grid;grid-template-columns:repeat(2,minmax(280px,420px));justify-content:center;gap:24px;padding:48px 20px}}
section{{background:white;border-radius:12px;box-shadow:0 2px 12px #17203322;padding:28px;display:flex;flex-direction:column;min-height:210px}}
section h2{{font-size:20px;margin:0 0 12px}}
section p{{color:#526174;line-height:1.5;flex:1}}
a.button{{display:inline-block;background:#2563eb;color:white;text-decoration:none;text-align:center;border-radius:8px;padding:12px 16px;font-weight:600}}
@media(max-width:700px){{main{{grid-template-columns:minmax(260px,420px)}}}}
</style></head>
<body><header><h1>Cloud FinOps Suite</h1>
<p>Select a dashboard to open it separately on port {port}.</p></header>
<main><section><h2>Cloud Cost Prediction and Optimization</h2>
<p>Multi-cloud cost ingestion, forecasting, anomaly detection, and approval-controlled remediation.</p>
<a class="button" href="/cost-optimization/">Open dashboard</a></section>
<section><h2>CloudOptima</h2>
<p>CSV-based cost intelligence, predictions, waste detection, and optimization recommendations.</p>
<a class="button" href="/cloudoptima/">Open dashboard</a></section></main></body></html>""".encode()


class MergedGateway(ThreadingHTTPServer):
    allow_reuse_address = True


def run_merged(port: int) -> int:
    cost_port = free_port()
    optima_port = free_port()
    children = [
        start_project(COST_PROJECT, "app.main:app", cost_port),
        start_project(OPTIMA_PROJECT, "main:app", optima_port),
    ]

    class RootHandler(GatewayHandler):
        routes = {
            "cost": ("127.0.0.1", cost_port),
            "optima": ("127.0.0.1", optima_port),
        }

        def do_GET(self) -> None:
            if urlsplit(self.path).path == "/":
                body = landing_page(port)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

    server = MergedGateway(("0.0.0.0", port), RootHandler)
    print(f"Merged dashboards: http://127.0.0.1:{port}/")
    print("Stop with Ctrl+C.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
    return 0


def run_single(project: str, port: int) -> int:
    if project == "cost":
        child = start_project(COST_PROJECT, "app.main:app", port)
    else:
        child = start_project(OPTIMA_PROJECT, "main:app", port)
    print(f"{project} dashboard: http://127.0.0.1:{port}/")
    try:
        return child.wait()
    except KeyboardInterrupt:
        child.terminate()
        return child.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Cloud FinOps projects.")
    parser.add_argument(
        "--project",
        choices=("merged", "cost", "optima"),
        default="merged",
        help="Run both projects or one project only (default: merged).",
    )
    parser.add_argument("--port", type=int, default=8000, help="Public port (default: 8000).")
    args = parser.parse_args()
    return run_merged(args.port) if args.project == "merged" else run_single(args.project, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
