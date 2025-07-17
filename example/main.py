import sys

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python main.py <filename>")
        sys.exit(1)
    filename = sys.argv[1]
    with open(filename, 'r') as f:
        code = f.read()
    # Use exec to execute the code and call is_prime(7) if present
    namespace = {}
    exec(code, namespace)