import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import setuptools, sssekai

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="sssekai",
    version=sssekai.__version__,
    author="greats3an",
    author_email="greats3an@gmail.com",
    description="Project SEKAI Asset Utility / PJSK 资源工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mos9527/sssekai",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    install_requires=[        
        "msgpack",
        "requests",
        "pycryptodome",        
        "unitypy >= 1.23.0",
        "tqdm",
        "coloredlogs",
    ],
    extras_require={"gui": ["GooeyEx>=0.0.8"], "il2cpp": ["lief"]},
    entry_points={
        "console_scripts": [
            "sssekai = sssekai.__main__:__main__",
            "sssekai-gui = sssekai.__gui__:__main__",
        ],
        "fsspec.specs": ["abcache = sssekai.abcache.fs.AbCacheFilesystem"],
    },
    python_requires=">=3.10",
)
