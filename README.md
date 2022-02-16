# readme
- goto-python only work with python 3.9, idk about 3.10.
- use it at your own risk, the author of this module does not fucking care if there is a problem with your app caused by this module.

# features
- does not add unnecessary `NOP` instructions to the code.
- automatically add push/pop block instructions if necessary.

# limitations
- can't jump into 'with', 'for', 'except', and 'finally' block. but can jump out of it.

# usage and examples
it's actually very simple, there's only two keyword, `goto` and `label`.

`label` define a label.
`goto` goto into the given label.

it can be used as a decorator of a function, or by patching a code object:
```py
from goto import with_goto, patch
import dis

# --- as a decorator ---
@with_goto
def inputpassword(maxretries):
  label .retry
  if maxretries == 0:
    return False

  pw = input("password: ")
  if pw != "1234":
    maxretries -= 1
    goto .retry

  return True

# --- patching code object ---
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

# how does it work?
basically it just replaces goto instruction with `JUMP_ABSOLUTE`.

#
have a look at this module [brandtbucher/hax](https://github.com/brandtbucher/hax),
it can do the same job as goto-python does, but it requires you to have basic knowledge of python bytecode,
and i guess its portable between python version?
