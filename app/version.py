import os

APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
GIT_SHA = os.getenv("GIT_SHA", "unknown")
BUILD_TIME = os.getenv("BUILD_TIME", "unknown")
