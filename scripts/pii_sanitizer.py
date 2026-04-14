import re
from flask import Flask, request, jsonify

PII_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"\b\d{10}\b"),
    "api_key": re.compile(r"\bapi[_-]?key\s*=\s*['\"]?[A-Za-z0-9]+['\"]?"),
    "password": re.compile(r"\bpassword\s*=\s*['\"]?[A-Za-z0-9]+['\"]?"),
    "secret": re.compile(r"\bsecret\s*=\s*['\"]?[A-Za-z0-9]+['\"]?"),
}

MASK = "***REDACTED***"

def sanitize_line(line: str) -> str:
    """Mask PII patterns in a single line of code."""
    for label, pattern in PII_PATTERNS.items():
        line = pattern.sub(f"{label}={MASK}", line)
    return line

def sanitize_file(input_path: str, output_path: str) -> str:
    """Read a file, sanitize PII, and write to a new file."""
    with open(input_path, "r", encoding="utf-8") as infile, \
         open(output_path, "w", encoding="utf-8") as outfile:
        for line in infile:
            outfile.write(sanitize_line(line))
    return f"Sanitized file written to {output_path}"

# --- JSON-RPC Server ---
app = Flask(__name__)

@app.route("/rpc", methods=["POST"])
def rpc_handler():
    req = request.get_json(force=True)
    if req.get("jsonrpc") != "2.0":
        return jsonify({"error": "Invalid JSON-RPC"}), 400

    method = req.get("method")
    params = req.get("params", {})
    rpc_id = req.get("id")

    try:
        if method == "pii_sanitize":
            input_path = params["input_path"]
            output_path = params.get("output_path", "sanitized_output.txt")
            result = sanitize_file(input_path, output_path)
            return jsonify({"jsonrpc": "2.0", "result": result, "id": rpc_id})
        else:
            return jsonify({"jsonrpc": "2.0", "error": "Unknown method", "id": rpc_id}), 400
    except Exception as e:
        return jsonify({"jsonrpc": "2.0", "error": str(e), "id": rpc_id}), 500

if __name__ == "__main__":
    app.run(port=5001)