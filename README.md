# Installation
make sure you are using python 3.9

```
pip install -U goto-label
```

**NOTE: support for python >=3.10 is very unstable.**

# Usage
a simple example:

```py
from goto import with_goto
from goto import goto, label  # optional, for linter purpose

@with_goto
def x():
    goto .end
    print("this will not print")
    label .end
    print("this will print")
```

- use `label .NAME` to define a label.
- use `goto .NAME` to goto into a label.

# Thanks
this project was inspired by [snoack/python-goto](https://github.com/snoack/python-goto) .\
since the project seems to have been discontinued, I created this.
