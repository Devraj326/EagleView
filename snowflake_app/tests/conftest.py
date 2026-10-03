import sys
from pathlib import Path

# So `from sf_lib import ...` resolves the same way it does for the real app,
# without needing snowflake_app installed as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
