from setuptools import setup, find_packages

setup(
    name="knowflow",
    version="0.1.0",
    description="Agent Knowledge Pipeline — Storage-agnostic, KB-agnostic, plug-and-play",
    author="qypvip",
    author_email="yanpeng898@gmail.com",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=[
        "pyyaml>=5.1",
    ],
    extras_require={
        "s3": ["boto3"],
        "notion": ["notion-client"],
        "ima": ["requests"],
    },
    entry_points={
        "console_scripts": [
            "knowflow=knowflow.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
