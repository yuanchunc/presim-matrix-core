"""
预演沙盘 PreSim Matrix - 打包配置

Python 开源包标准 setup，支持 pip install -e .
"""

from setuptools import find_packages, setup

try:
    with open("README.md", "r", encoding="utf-8") as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = ""

setup(
    name="presim-matrix-core",
    version="0.1.0",
    description="预演沙盘 PreSim Matrix - 微内核+插件注册表架构的仿真预演框架",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="PreSim Matrix Contributors",
    author_email="",
    url="https://github.com/presim-matrix/presim-matrix-core",
    license="Apache-2.0",
    packages=find_packages(exclude=["examples", "docs", "tests", "ui"]),
    python_requires=">=3.10",
    install_requires=[
        "langgraph>=0.2.0,<0.3.0",
        "langchain-core>=0.3.0,<0.4.0",
        "langchain>=0.3.0,<0.4.0",
        "chromadb>=0.5.0,<0.6.0",
        "streamlit>=1.40.0,<2.0.0",
        "pydantic>=2.0.0,<3.0.0",
        "pyyaml>=6.0,<7.0",
        "openai>=1.0.0,<2.0.0",
        "google-generativeai>=0.8.0,<0.9.0",
        "dashscope>=1.20.0,<2.0.0",
        "typing-extensions>=4.0.0",
    ],
    extras_require={
        "dev": ["pytest", "pytest-cov", "ruff", "mypy"],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="simulation, langgraph, agent, llm, presim",
)
