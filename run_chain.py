import requests, yaml

def call_rpc(url, method, params):
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    resp = requests.post(url, json=payload)
    return resp.json().get("result")

def run_chain(repo_path=".", commit_hash="HEAD"):
    with open("agent.yml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for agent in config.get("agents", []):
        print(f"Running {agent['name']}...")
        for skill in agent.get("skills", []):
            if skill == "pii-sanitizer":
                result = call_rpc("http://localhost:5001/rpc", "pii_sanitize", {"repo": repo_path})
            elif skill == "git-code-review":
                result = call_rpc("http://localhost:5002/rpc", "git_review", {"repo": repo_path, "commit": commit_hash})
            elif skill == "llm-code-review":
                result = call_rpc("http://localhost:5003/rpc", "llm_review", {"repo": repo_path, "commit": commit_hash})
            print(result)

if __name__ == "__main__":
    run_chain()