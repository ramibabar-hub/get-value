"""
backend/services/_key_loader.py
Streamlit-free API key loader.

Priority: os.environ → .env file (two directories up from this file).
Does NOT touch st.secrets — this module must be safe to import outside Streamlit.
"""

import os


def load_key(env_var: str) -> str:
    """
    Load an API key by environment variable name.

    Search order:
      1. os.environ  (works for Docker, CI, or shell-exported vars)
      2. .env file at the workspace root  (local development)

    Returns empty string if not found.
    """
    # 1. Environment variable
    val = os.environ.get(env_var, "").strip()
    if val:
        return val

    # 2. .env file  (workspace_root/.env)
    env_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    )
    if os.path.isfile(env_path):
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith(f"{env_var}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")

    return ""
