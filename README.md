### installation

compatible with python 3.9 or newer.\
tested with python 3.9.
```
pip install goto-label
```

### readme

- goto-python only work with python 3.9, idk about 3.10.
- use at your own risk, the author of this module does not care if there is a problem with your app caused by this module.

### features

- does not add unnecessary `NOP` instructions to the code.
- automatically add push/pop block instructions if necessary.\
  for example, if you jump out of `for` block, it automatically pop the iterator from the stack (as `break` does).

### limitations

- can't jump into `with`, `for`, `except`, and `finally` block. **but can jump out of it.**

### usage and examples

it's actually very simple, there's only two keyword, `goto` and `label`.\
`label` define a label.
`goto` goto into the given label.

1. as a decorator of a function:

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

2. by patching code object:

```py
from goto import patch
import dis

code = compile("goto .lbl; label .lbl;", "<string>", "exec")
newcode = patch(code)
print("original:")
dis.dis(code)
print("patched:")
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
# patched:
#  1       0 JUMP_ABSOLUTE        2
#    >>    2 LOAD_CONST           0 (None)
#          4 RETURN_VALUE
```

### examples of good gotos in python (IMO)

since python does not have labeled break/continue, we can use goto to do it.

1. to break out of nested loop
```py
for _ in ...:
  for _ in ...:
    if should_break:
      goto .br  # break outer loop
label .br
```

2. to continue outer from inner loop
```py
for _ in ...:
  for _ in ...:
    if should_continue:
      goto .con  # continue outer loop
  label .con
```

### how does it work?

basically it just replaces goto instruction with `JUMP_ABSOLUTE`.

#

have a look at this module [brandtbucher/hax](https://github.com/brandtbucher/hax),
it can do the same job as goto-python does, but it requires you to have basic knowledge of python bytecode,
and i guess it's portable between python version?
