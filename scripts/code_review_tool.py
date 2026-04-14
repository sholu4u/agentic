from flask import Flask, request, jsonify
import subprocess, shutil

app = Flask(__name__)

def _resolve_git_exe():
    git_exe = shutil.which("git")
    if git_exe:
        return git_exe
    raise RuntimeError("git not installed")

def _run_git(repo_path, args):
    git_exe = _resolve_git_exe()
    return subprocess.check_output([git_exe, "-C", repo_path, *args], text=True)

def run_git_review(repo_path, commit_hash):
    diff = _run_git(repo_path, ["show", "--no-ext-diff", "--text", "--format=", "--patch", commit_hash])
    return f"Code review diff for commit {commit_hash}:\n{diff}"

@app.route("/rpc", methods=["POST"])
def rpc_handler():
    req = request.get_json(force=True)
    if req.get("jsonrpc") != "2.0":
        return jsonify({"error": "Invalid JSON-RPC"}), 400

    method = req.get("method")
    params = req.get("params", {})
    rpc_id = req.get("id")

    try:
        if method == "git_review":
            repo = params["repo"]
            commit = params["commit"]
            result = run_git_review(repo, commit)
            return jsonify({"jsonrpc": "2.0", "result": result, "id": rpc_id})
        else:
            return jsonify({"jsonrpc": "2.0", "error": "Unknown method", "id": rpc_id}), 400
    except Exception as e:
        return jsonify({"jsonrpc": "2.0", "error": str(e), "id": rpc_id}), 500

if __name__ == "__main__":
    app.run(port=5002)