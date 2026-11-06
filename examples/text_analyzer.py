"""Calculate SHA256 checksum and word stats of a given text."""
import sys
import hashlib

def main():
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    if not text:
        text = "Hello from Universal MCP Bridge!"
    
    sha = hashlib.sha256(text.encode()).hexdigest()
    words = len(text.split())
    chars = len(text)
    
    print(f"Stats:")
    print(f"  Length: {chars} characters")
    print(f"  Word count: {words} words")
    print(f"  SHA-256: {sha}")

if __name__ == "__main__":
    main()
