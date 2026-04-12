import subprocess, yaml

def run_chain(repo_path=".", commit_hash="HEAD"):
    with open("./agent.yml") as f:
        config = yaml.safe_load(f)

    for agent in config.get("agents", []):
        print(f"Running {agent['name']}...")
        for skill in agent.get("skills", []):
            if skill == "pii-sanitizer":
                subprocess.run(["python", "scripts/pii_sanitizer.py"], check=True)
            elif skill == "git-code-review":
                subprocess.run([
                    "python", "scripts/code_review_tool.py",
                    "--repo", repo_path,
                    "--commit", commit_hash
                ], check=True)
            elif skill == "llm-code-review":
                subprocess.run([
                    "python", "scripts/llm_review_tool.py",
                    "--repo", repo_path,
                    "--commit", commit_hash
                ], check=True)

if __name__ == "__main__":
    run_chain()