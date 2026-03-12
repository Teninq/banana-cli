from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-banana-slides",
    version="1.1.0",
    description="CLI harness for Banana Slides – AI-powered PPT generation",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0",
        "requests>=2.28",
        "rich>=13.0",
        "python-pptx>=1.0",
    ],
    extras_require={
        "local": [
            "google-genai>=1.0",
            "openai>=1.0",
            "Pillow>=10.0",
            "tenacity>=8.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-banana-slides=cli_anything.banana_slides.banana_slides_cli:cli",
        ],
    },
    python_requires=">=3.9",
)
