import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from l5k_sim.ir import Controller, Instruction, Program, Project, Routine, Rung, Tag
from l5k_sim.server import SimService, make_handler


def _project():
    r = Rung(0, None, [Instruction("XIC", ["a"], ""), Instruction("OTE", ["y"], "")], "")
    prog = Program("P", "Main", [Tag("a", "BOOL", "P", None, "0", None), Tag("y", "BOOL", "P", None, "0", None)],
                   [Routine("Main", None, [r])])
    return Project(Controller("C", "x", [], [], [], [prog]))


def test_simservice_step_force_reset():
    svc = SimService(_project())
    assert svc.state()["tags"]["programs"]["P"]["y"] is False
    svc.force("P", "a", True)
    s = svc.step()
    assert s["tags"]["programs"]["P"]["y"] is True   # forced a -> XIC -> OTE
    r = svc.reset()
    assert r["tags"]["programs"]["P"]["y"] is False   # fresh engine
    assert r["time_ms"] == 0


def _serve(svc, web_dir="."):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(svc, web_dir))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def _req(httpd, method, path, body=None):
    conn = HTTPConnection("127.0.0.1", httpd.server_address[1])
    try:
        payload = json.dumps(body).encode() if body is not None else None
        conn.request(method, path, body=payload, headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = resp.read()
        return resp.status, (json.loads(data) if data and resp.getheader("Content-Type", "").startswith("application/json") else data)
    finally:
        conn.close()


def test_http_api_ir_and_step():
    svc = SimService(_project())
    httpd = _serve(svc)
    try:
        status, ir = _req(httpd, "GET", "/api/ir")
        assert status == 200 and ir["programs"][0]["name"] == "P"
        status, st = _req(httpd, "POST", "/api/force", {"scope": "P", "operand": "a", "value": True})
        assert status == 200
        status, st = _req(httpd, "POST", "/api/step")
        assert status == 200 and st["tags"]["programs"]["P"]["y"] is True
        status, _ = _req(httpd, "GET", "/nope")
        assert status == 404
    finally:
        httpd.shutdown()


def test_force_missing_key_returns_400():
    svc = SimService(_project())
    httpd = _serve(svc)
    try:
        status, _ = _req(httpd, "POST", "/api/force", {"scope": "P"})  # missing operand/value
        assert status == 400
    finally:
        httpd.shutdown()
