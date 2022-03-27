# Installation
Compatible with python 3.9 or newer.\
tested with python 3.9.
```
pip install goto-label
```

- goto-python only work with python 3.9, idk about 3.10.
- use at your own risk, the author of this module is not responsible if there is a problem with your app.

### Features
- does not add unnecessary `NOP` instructions to the code.
- automatically add push/pop block instructions if necessary.\
  for example, if you jump out of `for` block, it automatically pop the iterator from the stack (as `break` does).

### Limitations
- can't jump into `with`, `for`, `except`, and `finally` block. **but can jump out of it.**

# Syntax
- `goto .name` jump to `name`.
- `label .name` define label `name`.

# Usage
1\. as a decorator of a function

```py
from goto import with_goto

@with_goto
def example():
  goto .end
  print("this will not print")
  label .end
  print("this will print")

example()

# output:
# this will print
```

2\. patching code object

```py
from goto import patch
import dis

# make code object
codestring = "goto .lbl; label .lbl"
code = compile(codestring, "<string>", "exec")

# patch code object
newcode = patch(code)

print("original:")
dis.dis(code)
print("modified:")
dis.dis(newcode)

# original:
#  1       0 LOAD_NAME            0 (goto)
#          2 LOAD_ATTR            1 (lbl)
#          4 POP_TOP
#          6 LOAD_NAME            2 (label)
#          8 LOAD_ATTR            1 (lbl)
#         10 POP_TOP
#         12 LOAD_CONST           0 (None)
#         14 RETURN_VALUE
# modified:
#  1       0 JUMP_ABSOLUTE        2
#    >>    2 LOAD_CONST           0 (None)
#          4 RETURN_VALUE
```

### Examples of good gotos in python (IMO)
labeled break/continue

```py
for _ in ...:
  for _ in ...:
    if should_break:
      goto .br  # break outer loop
label .br
```
```py
for _ in ...:
  for _ in ...:
    if should_continue:
      goto .con  # continue outer loop
  label .con
```

#
this module [brandtbucher/hax](https://github.com/brandtbucher/hax),
can do the same job as goto-python does, but it requires you to have basic knowledge of python bytecode.
