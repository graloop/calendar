# Makes the connector password's hash, to paste into Portainer as MCP_PASSWORD_HASH:
#   docker exec -it agenda python -m app.mcp.hashpw
# Asks for the password twice (nothing shows while typing) and prints only the hash.

import getpass
import sys

from .passwords import hash_password

MIN_LENGTH = 12  # It guards a public login page: long beats clever.


def main() -> int:
    password = getpass.getpass("Connector password: ")
    if len(password) < MIN_LENGTH:
        print(f"Use at least {MIN_LENGTH} characters.", file=sys.stderr)
        return 1
    if getpass.getpass("Same password again: ") != password:
        print("The two didn't match. Nothing was made.", file=sys.stderr)
        return 1
    print(hash_password(password))
    print("Paste this line into the stack as MCP_PASSWORD_HASH, then Pull and redeploy.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
