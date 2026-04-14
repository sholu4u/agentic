from flask import Flask, request, jsonify
import subprocess, shutil, os, yaml, openai
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=".cursor/.env")
openai.api_key = os.getenv("OPENAI_API_KEY")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
anthropic_client = Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None

app = Flask(__name__)

def _resolve_git_exe():
    git_exe = shutil.which("git")
    if git_exe:
        return git_exe
    raise RuntimeError("git not installed")

def _run_git(repo_path, args):
    git_exe = _resolve_git_exe()
    return subprocess.check_output([git_exe, "-C", repo_path, *args], text=True)

def _get_diff(repo_path, commit_hash):
    return _run_git(repo_path, ["show", "--no-ext-diff", "--text", "--format=", "--patch", commit_hash])

def get_provider_and_model_from_agent_config():
    provider, model = "openai", "gpt-4-turbo"
    try:
        with open("./agent.yml", "r") as f:
            config = yaml.safe_load(f)
        for agent in config.get("agents", []):
            if agent["id"] == "reviewer":
                provider = agent.get("config", {}).get("llm_provider", provider)
                model = agent.get("config", {}).get("model", model)
    except Exception:
        pass
    return provider, model

def llm_review(diff_text, provider="openai", model=None):
    prompt = f"""
    You are a senior code reviewer.
    Review the following git diff for vulnerabilities, insecure patterns, and style issues.
    Provide actionable feedback, but redact any secrets:

    {diff_text}
    """
    if provider == "openai":
        response = openai.ChatCompletion.create(
            model=model or "gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600
        )
        return response["choices"][0]["message"]["content"]

    elif provider == "anthropic" and anthropic_client:
        model = model or "claude-opus-4.6"
        response = anthropic_client.messages.create(
            model=model,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    else:
        raise RuntimeError("No valid LLM provider or API key configured.")

@app.route("/rpc", methods=["POST"])
def rpc_handler():
    req = request.get_json(force=True)
    if req.get("jsonrpc") != "2.0":
        return jsonify({"error": "Invalid JSON-RPC"}), 400

    method = req.get("method")
    params = req.get("params", {})
    rpc_id = req.get("id")

    try:
        if method == "llm_review":
            repo = params["repo"]
            commit = params["commit"]
            provider, model = get_provider_and_model_from_agent_config()
            diff = _get_diff(repo, commit)
            result = llm_review(diff, provider=provider, model=model)
            return jsonify({"jsonrpc": "2.0", "result": result, "id": rpc_id})
        else:
            return jsonify({"jsonrpc": "2.0", "error": "Unknown method", "id": rpc_id}), 400
    except Exception as e:
        return jsonify({"jsonrpc": "2.0", "error": str(e), "id": rpc_id}), 500

if __name__ == "__main__":
    app.run(port=5003)