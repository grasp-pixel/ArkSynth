"""Allow running as: python -m tools.extractor"""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
