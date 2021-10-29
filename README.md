# Installation
make sure you are using python 3.9

```
pip install -U goto-label
```

**NOTE: support for python >=3.10 is very unstable, please run the test before using.**

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

# Limitation
```py
@with_goto
def x():
    try:
        pass
    finally:
        label .a
```

here we define the label "a" once. but if you run the code:

```py
SyntaxError: ambiguous label name: 'a'. at line 10
```

it's not a bug, but why is it?

let's try to disassemble the code without modifying it:
```
  7           0 SETUP_FINALLY           10 (to 12)

  8           2 POP_BLOCK

 10           4 LOAD_GLOBAL              0 (label)
              6 LOAD_ATTR                1 (a)
              8 POP_TOP
             10 JUMP_FORWARD             8 (to 20)
        >>   12 LOAD_GLOBAL              0 (label)
             14 LOAD_ATTR                1 (a)
             16 POP_TOP
             18 RERAISE
        >>   20 LOAD_CONST               0 (None)
             22 RETURN_VALUE
```

because the `finally` block is copy pasted by python.\
look at the instructions, there are two definitions of label "a".

# Thanks
this project was inspired by [snoack/python-goto](https://github.com/snoack/python-goto) .\
since the project seems to have been discontinued, I created this.
