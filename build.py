#!/usr/bin/env python
"""Entry point: rebuild the Adapt course JSON from the storyboard .docx.

    python build.py --help
"""

from __future__ import annotations

import sys

from adapt_builder.cli import main

if __name__ == "__main__":
    sys.exit(main())
