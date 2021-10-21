from setuptools import setup
import pathlib


HERE = pathlib.Path(__file__).parent
README = (HERE / "README.md").read_text()


setup(
    name="goto-python",
    version="0.1.1",
    description="A function decorator, that rewrites the bytecode, to enable goto in Python",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/structuredman/goto-python",
    author="StructuredMan",
    python_requires=">=3.6",
    py_modules=["goto"]
)
