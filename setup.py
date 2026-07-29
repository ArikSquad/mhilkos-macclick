"""
Build a standalone AutoClicker.app using py2app.

Run this ON YOUR INTEL MAC (not here) with:

    pip3 install py2app pynput
    python3 setup.py py2app

The finished app will be in the "dist" folder as AutoClicker.app.
Building on an Intel Mac with Intel Python naturally produces an
Intel (x86_64) app bundle.
"""

from setuptools import setup

APP = ["autoclicker.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "packages": ["pynput"],
    "plist": {
        "CFBundleName": "AutoClicker",
        "CFBundleDisplayName": "AutoClicker",
        "CFBundleIdentifier": "com.example.autoclicker",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "NSHumanReadableCopyright": "For personal use",
        "LSUIElement": False,
        "NSAppleEventsUsageDescription": "AutoClicker needs this to simulate clicks.",
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
