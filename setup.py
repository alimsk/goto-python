from setuptools import setup
import pathlib


HERE = pathlib.Path(__file__).parent
README = (HERE / "README.md").read_text()


setup(
    name="goto-python",
    version="0.1.0",
    description="A function decorator, that rewrites the bytecode, to enable goto in Python",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/alimsk/goto-python",
    author="Ali M",
    python_requires=">=3.9",
    py_modules=["goto"]
)
