# Installation
```
pip install goto-python
```
tested in python 3.9.\
I'm not sure if this will work well before 3.9.

if you want to use it in versions below 3.9, you have to manually clone this repo and then test it yourself.\
unexpected errors may occur if you use this below 3.9, so i prefer to set requirement version to `>=3.9`

but obviously, the minimum version is 3.6, because it uses 2 bytes for each instruction:
> Changed in version 3.6: Use 2 bytes for each instruction. Previously the number of bytes varied by instruction.\
> *from the python 3 dis module [documentation](https://docs.python.org/3/library/dis.html)*

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
