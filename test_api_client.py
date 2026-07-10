"""
API smoke test — 使用标准库 urllib 验证 FastAPI 三端点。

启动方式：
  1. 启动 API 服务: python main_api.py
  2. 运行测试:    python test_api_client.py
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
FAILED = 0
PROJECT_ROOT = Path(__file__).resolve().parent


def api_request(method, path, data=None, files=None):
    """简单的 HTTP 请求封装。"""
    url = f"{BASE_URL}{path}"
    if method == "GET":
        req = urllib.request.Request(url, method="GET")
    elif method == "POST":
        if data:
            req = urllib.request.Request(url, data=data, method="POST")
        else:
            req = urllib.request.Request(url, method="POST")
    else:
        raise ValueError(f"Unsupported method: {method}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        return e.code, json.loads(body) if body else {"detail": str(e)}
    except urllib.error.URLError as e:
        return None, {"error": str(e.reason)}


def start_server():
    """启动 API 服务子进程。"""
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "main_api.py")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "LITERATURE_PROVIDER": "mock", "PYTHONIOENCODING": "utf-8"},
    )
    # 等待服务就绪
    for _ in range(30):
        try:
            urllib.request.urlopen(f"{BASE_URL}/health", timeout=1)
            return proc
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("API 服务启动超时")


def test_health():
    global FAILED
    print("\n=== Test: Health ===")
    status, data = api_request("GET", "/health")
    if status == 200 and data.get("status") == "ok":
        print("[OK] Health check")
    else:
        print(f"[FAIL] Health check: {status} {data}")
        FAILED += 1


def test_submit_topic_only():
    global FAILED
    print("\n=== Test: Submit topic-only ===")
    body = urllib.parse.urlencode({"topic": "AI safety"}).encode("utf-8")
    status, data = api_request("POST", "/api/v1/jobs/submit", data=body)
    if status == 202 and "job_id" in data and data.get("provider") == "mock":
        print(f"[OK] Job created: {data['job_id']}")
        return data["job_id"]
    else:
        print(f"[FAIL] Submit: {status} {data}")
        FAILED += 1
        return None


def test_submit_file_upload():
    global FAILED
    print("\n=== Test: Submit file upload ===")
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("This is a test document about AI safety and alignment.\n")
        tmp = f.name

    try:
        # multipart form upload via urllib
        boundary = "----TestBoundary"
        body = []
        body.append(f"--{boundary}".encode())
        body.append(b'Content-Disposition: form-data; name="topic"')
        body.append(b"")
        body.append("AI document analysis".encode())
        body.append(f"--{boundary}".encode())
        body.append(f'Content-Disposition: form-data; name="file"; filename="{Path(tmp).name}"'.encode())
        body.append(b"Content-Type: text/plain")
        body.append(b"")
        with open(tmp, "rb") as fh:
            body.append(fh.read())
        body.append(f"--{boundary}--".encode())
        body_bytes = b"\r\n".join(body)

        req = urllib.request.Request(
            f"{BASE_URL}/api/v1/jobs/submit",
            data=body_bytes,
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("job_id"):
            print(f"[OK] File job created: {data['job_id']}")
            return data["job_id"]
        else:
            print(f"[FAIL] File submit: {data}")
            FAILED += 1
            return None
    finally:
        import os
        os.unlink(tmp)


def test_invalid_requests():
    global FAILED
    print("\n=== Test: Invalid requests ===")

    status, data = api_request("GET", "/api/v1/jobs/status/bad.job")
    if status == 400:
        print("[OK] Invalid job_id rejected")
    else:
        print(f"[FAIL] Invalid job_id: {status} {data}")
        FAILED += 1

    status, data = api_request("GET", "/api/v1/jobs/status/not_found_job")
    if status == 404:
        print("[OK] Missing valid job returns 404")
    else:
        print(f"[FAIL] Missing job: {status} {data}")
        FAILED += 1

    body = urllib.parse.urlencode({"topic": ""}).encode("utf-8")
    status, data = api_request("POST", "/api/v1/jobs/submit", data=body)
    if status == 400:
        print("[OK] Empty submit rejected")
    else:
        print(f"[FAIL] Empty submit: {status} {data}")
        FAILED += 1

    body = urllib.parse.urlencode({"topic": "AI", "provider": "unknown"}).encode("utf-8")
    status, data = api_request("POST", "/api/v1/jobs/submit", data=body)
    if status == 400:
        print("[OK] Unknown provider rejected")
    else:
        print(f"[FAIL] Unknown provider: {status} {data}")
        FAILED += 1

    boundary = "----InvalidUploadBoundary"
    parts = [
        f"--{boundary}".encode(),
        b'Content-Disposition: form-data; name="topic"',
        b"",
        b"Invalid upload",
        f"--{boundary}".encode(),
        b'Content-Disposition: form-data; name="file"; filename="payload.exe"',
        b"Content-Type: application/octet-stream",
        b"",
        b"not allowed",
        f"--{boundary}--".encode(),
    ]
    body_bytes = b"\r\n".join(parts)
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/jobs/submit",
        data=body_bytes,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        status = e.code
        data = json.loads(e.read().decode("utf-8"))

    if status == 400:
        print("[OK] Unsupported upload extension rejected")
    else:
        print(f"[FAIL] Unsupported extension: {status} {data}")
        FAILED += 1


def test_status(job_id):
    global FAILED
    print(f"\n=== Test: Status for {job_id} ===")
    for attempt in range(60):
        status, data = api_request("GET", f"/api/v1/jobs/status/{job_id}")
        if status != 200:
            print(f"[FAIL] Status: HTTP {status}")
            FAILED += 1
            return None
        state = data.get("status", "")
        current = data.get("current_task", "")
        print(f"  Poll {attempt+1}: status={state}, current_task={current}")
        if state in ("COMPLETED", "FAILED"):
            if state == "COMPLETED":
                print(f"[OK] Job completed")
            else:
                print(f"[FAIL] Job failed: {data.get('error')}")
                FAILED += 1
            return state
        time.sleep(2)
    print(f"[FAIL] Poll timeout")
    FAILED += 1
    return None


def test_result(job_id):
    global FAILED
    print(f"\n=== Test: Result for {job_id} ===")
    status, data = api_request("GET", f"/api/v1/jobs/result/{job_id}")
    if status == 200:
        report_len = len(data.get("report", ""))
        summary = data.get("context_summary", {})
        print(f"[OK] Result: report={report_len} chars, context_keys={summary.get('keys', [])}")
        assert report_len > 0, "Report should not be empty"
        assert data.get("provider_status", {}).get("provider") == "mock"
        assert isinstance(data.get("sources"), list)
        assert isinstance(data.get("tech_cases"), list)
        assert isinstance(data.get("policy_assessment"), list)
        assert isinstance(data.get("warnings"), list)
    elif status == 409:
        print(f"[WARN] Job not complete yet: {data.get('detail')}")
    else:
        print(f"[FAIL] Result: {status} {data}")
        FAILED += 1


def test_concurrent_isolation():
    global FAILED
    print("\n=== Test: Concurrent job isolation ===")
    # Submit two jobs
    body1 = urllib.parse.urlencode({"topic": "AI ethics"}).encode("utf-8")
    body2 = urllib.parse.urlencode({"topic": "climate change"}).encode("utf-8")

    _, r1 = api_request("POST", "/api/v1/jobs/submit", data=body1)
    _, r2 = api_request("POST", "/api/v1/jobs/submit", data=body2)

    j1 = r1.get("job_id")
    j2 = r2.get("job_id")
    if not j1 or not j2:
        print("[FAIL] Concurrent submit failed")
        FAILED += 1
        return

    print(f"  Job A: {j1}, Job B: {j2}")
    if j1 == j2:
        print(f"[FAIL] job_ids are identical")
        FAILED += 1
    else:
        print(f"[OK] Different job_ids generated")

    # Wait for both to complete
    for _ in range(60):
        _, s1 = api_request("GET", f"/api/v1/jobs/status/{j1}")
        _, s2 = api_request("GET", f"/api/v1/jobs/status/{j2}")
        st1 = s1.get("status", "")
        st2 = s2.get("status", "")
        if st1 in ("COMPLETED", "FAILED") and st2 in ("COMPLETED", "FAILED"):
            if st1 == "COMPLETED" and st2 == "COMPLETED":
                # Verify job_ids in state files
                _, d1 = api_request("GET", f"/api/v1/jobs/result/{j1}")
                _, d2 = api_request("GET", f"/api/v1/jobs/result/{j2}")
                jid1 = d1.get("job_id")
                jid2 = d2.get("job_id")
                if jid1 == jid2:
                    print(f"[FAIL] Result job_ids match ({jid1})")
                    FAILED += 1
                else:
                    print(f"[OK] Jobs isolated: A={jid1}, B={jid2}")
            return
        time.sleep(2)
    print("[FAIL] Concurrent poll timeout")
    FAILED += 1


# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Starting API server...")
    server = start_server()
    print(f"Server started (PID {server.pid})")

    try:
        test_health()
        test_invalid_requests()

        # Test 1: topic-only submit + poll + result
        job_id = test_submit_topic_only()
        if job_id:
            test_status(job_id)
            test_result(job_id)

        # Test 2: file upload
        file_job = test_submit_file_upload()
        if file_job:
            test_status(file_job)

        # Test 3: concurrent isolation
        test_concurrent_isolation()

    finally:
        print("\nShutting down server...")
        server.terminate()
        server.wait(timeout=10)

    print(f"\n{'='*50}")
    if FAILED:
        print(f"{FAILED} API test(s) FAILED.")
        sys.exit(1)
    else:
        print("All API tests PASSED.")
