
"""
Standalone entry script for packaging the GUI with PyInstaller.
This keeps package-relative imports intact.
"""

from make_practice_book.gui import main

if __name__ == "__main__":
    main()
