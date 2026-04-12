import re

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

def sanitize_file(input_path: str, output_path: str):
    """Read a file, sanitize PII, and write to a new file."""
    with open(input_path, "r", encoding="utf-8") as infile, \
         open(output_path, "w", encoding="utf-8") as outfile:
        for line in infile:
            outfile.write(sanitize_line(line))
    print(f"Sanitized file written to {output_path}")
