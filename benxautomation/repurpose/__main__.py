"""Direct executable entrypoint for python -m benxautomation.repurpose."""

import sys
from benxautomation.repurpose.cli import main

if __name__ == "__main__":
    sys.exit(main())
