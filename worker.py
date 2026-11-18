import json, os, re, sys, urllib.request

URL = os.environ["JOB_URL"]
CLIP = "https://hq.mega.dev/media/two-places/dispatch-2-c14d2d05.mp3"
session = None


def rpc(method, params=None, notify=False):
    global session
    body = {"jsonrpc": "2.0", "method": method}
    if not notify:
        body["id"] = 1
    if params is not None:
        body["params"] = params
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    if session:
        headers["Mcp-Session-Id"] = session
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        session = r.headers.get("Mcp-Session-Id", session)
        raw = r.read().decode()
    if notify or not raw.strip():
        return None
    if raw.lstrip().startswith("{"):
        msg = json.loads(raw)
    else:
        msg = json.loads([l[5:] for l in raw.splitlines() if l.startswith("data:")][-1])
    if "error" in msg:
        sys.exit(f"{method} failed: {msg['error']}")
    return msg["result"]


def call(name, args):
    res = rpc("tools/call", {"name": name, "arguments": args})
    text = res["content"][0]["text"]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "two-places-ci-worker", "version": "1"}})
rpc("notifications/initialized", notify=True)
skill = rpc("resources/read", {"uri": "skill://voice-to-memo/SKILL.md"})["contents"][0]["text"]
version = re.search(r'version:\s*"?(\d+)"?', skill).group(1)
print("skill voice-to-memo version", version)

t = call("transcribe", {"url": CLIP})
step = t["step"]
findings = [s for s in t["segments"] if re.search(r"\btram\b", s["text"], re.I)]
for s in t["segments"]:
    print(("FINDING " if s in findings else "talk    ") + f"{s['at']}  {s['text']}")

notes = []
for s in findings:
    note = f"{s['text']} @{s['at']}"
    step = call("memo_write", {"text": note, "step": step})["step"]
    notes.append(note)

back = call("memo_search", {"step": step})
step = back["step"]
print("memo_search:", json.dumps({k: v for k, v in back.items() if k != "step"})[:2000])

out = call("submit", {"result": "\n".join(notes), "skillVersion": version, "step": step})
print("SUBMIT", json.dumps(out))
