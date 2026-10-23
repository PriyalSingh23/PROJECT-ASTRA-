import torch  # Critical on macOS Apple Silicon: MUST be imported before any other C-extensions to prevent OpenBLAS linker collision (SIGSEGV 139)
import os
from typing import Optional
from flask import Flask, render_template, send_from_directory, request
from messaging.api import api_v1
from messaging.db import init_db, get_db_session, DEFAULT_DB_PATH
from messaging.retry_policy import RetryPolicy
from messaging.security_config import get_app_secret_key, is_production

TEMPLATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "templates"))
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist"))


def create_app(
    db_path: Optional[str] = None,
    station_id: Optional[str] = None,
    station_name: Optional[str] = None,
    port: Optional[int] = None,
    peer_url: Optional[str] = None,
) -> Flask:
    """Factory creating the Flask application for SHADOWCOMM Reliable Messaging & Research Platform."""
    app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
    app.config["SECRET_KEY"] = get_app_secret_key()
    if is_production():
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["SESSION_COOKIE_HTTPONLY"] = True
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    effective_db_path = db_path or DEFAULT_DB_PATH
    app.config["DB_PATH"] = effective_db_path
    app.config["STATION_ID"] = station_id
    app.config["STATION_NAME"] = station_name or ("Station Alpha" if station_id == "endpoint-a" else "Station Bravo" if station_id == "endpoint-b" else "Tactical Station")
    app.config["STATION_PORT"] = port or (5051 if station_id == "endpoint-a" else 5052 if station_id == "endpoint-b" else 5050)
    app.config["PEER_URL"] = peer_url

    # Initialize SQLite database and seed endpoints
    init_db(effective_db_path, station_id=station_id)

    # Recover stranded in-flight worker leases upon startup
    with get_db_session(db_path) as session:
        RetryPolicy.recover_stranded_leases(session)

    # Register API blueprint
    app.register_blueprint(api_v1)

    # CORS & Preflight handling for development Vite server (port 5173) and local host
    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        allowed = [
            "http://127.0.0.1:5050",
            "http://localhost:5050",
            "http://127.0.0.1:5051",
            "http://localhost:5051",
            "http://127.0.0.1:5052",
            "http://localhost:5052",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]
        if origin in allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Endpoint-Token"
        return response

    @app.route("/<path:dummy>", methods=["OPTIONS"])
    @app.route("/", methods=["OPTIONS"])
    def preflight_handler(dummy=""):
        return "", 204

    # Serve built React frontend from frontend/dist if available
    if os.path.exists(FRONTEND_DIST) and os.path.exists(os.path.join(FRONTEND_DIST, "index.html")):
        @app.route("/assets/<path:filename>")
        def frontend_assets(filename):
            return send_from_directory(os.path.join(FRONTEND_DIST, "assets"), filename)

        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_react(path):
            if path and os.path.exists(os.path.join(FRONTEND_DIST, path)):
                return send_from_directory(FRONTEND_DIST, path)
            return send_from_directory(FRONTEND_DIST, "index.html")

    # Fallback / standalone dispatch template route
    @app.route("/legacy")
    @app.route("/offline-messaging")
    def offline_ui():
        return render_template("offline_messaging.html")

    return app


def start_worker_supervisor(
    db_path: Optional[str] = None,
    poll_interval: float = 1.0,
    peer_url: Optional[str] = None,
):
    """Spawns an in-process background QueueWorker thread to process deliveries."""
    import threading
    from messaging.worker import QueueWorker
    worker = QueueWorker(
        worker_id="embedded-worker",
        db_path=db_path,
        poll_interval=poll_interval,
        peer_url=peer_url,
    )
    worker_thread = threading.Thread(
        target=worker.start,
        daemon=True,
        name="QueueWorkerSupervisorThread",
    )
    worker_thread.start()
    return worker, worker_thread


def main():
    import argparse
    parser = argparse.ArgumentParser(description="SHADOWCOMM Reliable Messaging & Research Platform")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5050, help="Port to bind (default: 5050)")
    parser.add_argument("--db", default=None, help="Path to SQLite database file")
    parser.add_argument("--station-id", default=None, help="Station identifier (e.g. endpoint-a or endpoint-b)")
    parser.add_argument("--station-name", default=None, help="Display name for this station")
    parser.add_argument("--peer-url", default=None, help="Remote peer API base URL (e.g. http://127.0.0.1:5052/api/v1)")
    parser.add_argument("--with-worker", dest="with_worker", action="store_true", default=True, help="Auto-spawn embedded delivery worker thread (default: True)")
    parser.add_argument("--no-worker", dest="with_worker", action="store_false", help="Disable embedded delivery worker thread")
    args = parser.parse_args()

    print("=" * 68)
    print("  SHADOWCOMM — Reliable Communications & Research Platform")
    print(f"  Web Interface:           http://{args.host}:{args.port}")
    print(f"  REST API Health Check:   http://{args.host}:{args.port}/api/v1/health")
    if args.station_id:
        print(f"  Station Identity:        {args.station_id} ({args.station_name or 'Configured'})")
    if args.peer_url:
        print(f"  Peer Forwarding Target:  {args.peer_url}")
    if args.with_worker:
        print("  Delivery Worker:         Embedded daemon active (supervising queue)")
        start_worker_supervisor(db_path=args.db, peer_url=args.peer_url)
    else:
        print("  Delivery Worker:         External daemon mode (--no-worker)")
    print("=" * 68)
    app = create_app(
        db_path=args.db,
        station_id=args.station_id,
        station_name=args.station_name,
        port=args.port,
        peer_url=args.peer_url,
    )
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
