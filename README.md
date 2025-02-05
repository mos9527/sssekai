# sssekai
[![Windows Build](https://github.com/mos9527/sssekai/actions/workflows/python-publish.yml/badge.svg)](https://github.com/mos9527/sssekai/blob/main/.github/workflows/python-publish.yml) [![Releases](https://img.shields.io/github/downloads/mos9527/sssekai/total.svg)](https://GitHub.com/mos9527/sssekai/releases/) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) 

Command-line tool (w/Python API support) for Project SEKAI (JP: プロジェクトセカイ カラフルステージ！ feat.初音ミク) game assets.

# Installing & Updating
**For Windows Users** : Builds are available [here](https://github.com/mos9527/sssekai/releases)

Python >=3.10 is required to run this tool.

You can install the latest version of `sssekai` from PyPI using pip:
```bash
pip install -U sssekai
```
To use the latest development version, you can install directly from GitHub:
```bash
pip install -U  git+https://github.com/mos9527/sssekai
```
## Using the GUI version
Additionally, you can use the GUI version of `sssekai` by installing the `[gui]` extra, which in turn installs [nicolasbraun's `Gooey` fork](https://github.com/nicolasbraun/Gooey)
```bash
pip install -U sssekai[gui]
```
Then you can run the GUI version by:
```bash
sssekai-gui
```
# Documentation
See the [wiki page!](https://github.com/mos9527/sssekai/wiki)

# See Also
https://github.com/mos9527/sssekai_blender_io

# License
MIT

# References
- https://github.com/K0lb3/UnityPy
- https://mos9527.github.io/tags/project-sekai/