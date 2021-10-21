# Installation
```
pip install goto-python
```
tested in python 3.9 and 3.8.

the minimum version is (probably) 3.6, because it uses 2 bytes for each instruction:
> Changed in version 3.6: Use 2 bytes for each instruction. Previously the number of bytes varied by instruction.\
> *from the python 3 dis module [documentation](https://docs.python.org/3/library/dis.html)*

it's just my guess, you can just try it yourself and see if it works.

currently, it doesn't support python 3.10, but maybe I'll create it in a separate repo in the future.
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

# Limitations
implicit push/pop block is not supported below python 3.9,
this means you can't enter/exit a block using goto:
```py
goto .enter  # SyntaxError
try:
    label .enter
except: pass
```
```py
label .exit
try:
    goto .exit  # SyntaxError
except: pass
```
keep in mind that `if/for/while` does not create a block, you can still do this:
```py
label .begin
if x == y:
    goto .begin
else:
    goto .end
label .end
```

below is the list of statements that can create a block:
- with statement
- async with
- try catch

# Thanks
this project was inspired by [snoack/python-goto](https://github.com/snoack/python-goto) .\
since the project seems to have been discontinued, I created this.
