"""Setup script for zuper_connector package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="zuper-connector",
    version="1.0.0",
    author="Your Name",
    description="Python connector for the Zuper Field Service Management API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/samfost22/Zuper-data",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
    ],
    extras_require={
        "dashboard": [
            "streamlit>=1.28.0",
            "pandas>=2.0.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "zuper=zuper_connector.cli:main",
            "zuper-dashboard=dashboard.run:main",
        ],
    },
)
