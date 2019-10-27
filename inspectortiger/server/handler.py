import ast
import json
from http.server import BaseHTTPRequestHandler

from inspectortiger.inspector import Inspector
from inspectortiger.session import Session
from inspectortiger.utils import Group, logger


class InspectorServer(BaseHTTPRequestHandler):
    def do_GET(self, *args, **kwargs):
        self._respond(200)

    def do_POST(self, *args, **kwargs):
        content_length = int(self.headers.get("Content-Length", "-1"))
        body = self.rfile.read(content_length)
        try:
            body = json.loads(body.decode())
        except json.JSONDecodeError:
            logger.exception("Couldn't parse body")
            return self.fail("Request body should be JSON!")

        source = body.get("source")
        if source is None:
            logger.exception("Missing body item")
            return self.fail("Request body should contain a source field!")

        try:
            source = ast.parse(source)
        except (SyntaxError, TypeError) as exc:
            logger.exception("Couldn't parse source")
            return self.fail(
                message=f"Couldn't parse the source code. {exc!r}"
            )

        session = Session()
        session.start()

        inspection = session.single_inspection(source)
        return self.respond(
            status="success",
            result=dict(session.group_by(inspection, group=Group.LINENO)),
        )

    def _respond(self, code):
        self.send_response(code)
        self.end_headers()

    def respond(self, code=200, **data):
        self.wfile.write(json.dumps(data).encode())

    def fail(self, message, code=400):
        self.respond(code=code, status="fail", message=message)
