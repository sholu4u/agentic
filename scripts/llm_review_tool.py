import argparse
import subprocess
import shutil
import os
from dotenv import load_dotenv
import openai
from anthropic import Anthropic
import yaml

# Load environment variables from .cursor/.env
load_dotenv(dotenv_path=".cursor/.env")

# Configure API keys
openai.api_key = os.getenv("OPENAI_API_KEY")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

# Initialize Anthropic client if key is present
anthropic_client = Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None

def _resolve_git_exe():
    git_exe = shutil.which("git")
    if git_exe:
        return git_exe
    raise RuntimeError("git is not installed or not on PATH.")

def _run_git(repo_path, args):
    git_exe = _resolve_git_exe()
    return subprocess.check_output([git_exe, "-C", repo_path, *args], text=True)

def _get_diff(repo_path, commit_hash):
    return _run_git(repo_path, ["show", "--no-ext-diff", "--text", "--format=", "--patch", commit_hash])

def get_provider_and_model_from_agent_config():
    """Read agent.yml to decide which LLM provider and model to use."""
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

def llm_review(diff_text: str, provider: str = "openai", model: str = None) -> str:
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
        # Use official Anthropic model identifiers
        model = model or "claude-opus-4.6"
        response = anthropic_client.messages.create(
            model=model,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    else:
        raise RuntimeError("No valid LLM provider or API key configured.")

def main():
    parser = argparse.ArgumentParser(description="LLM-based code review")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--provider", choices=["openai", "anthropic"], default=None)
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    # Decide provider/model: CLI flag overrides agent.yml
    provider, model = get_provider_and_model_from_agent_config()
    if args.provider:
        provider = args.provider
    if args.model:
        model = args.model

    diff = _get_diff(args.repo, args.commit)
    feedback = llm_review(diff, provider=provider, model=model)
    print("LLM Review Feedback:\n")
    print(feedback)

if __name__ == "__main__":
    main()