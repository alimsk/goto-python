from dataclasses import dataclass
import typing as t
import types
import dis


# for linter purpose
goto: t.Any = None
label: t.Any = None


@dataclass(init=False, repr=False)
class _Instruction:
    """a mutable instruction"""
    id: int
    opcode: int
    arg: int

    # optional attribute
    jump_target: t.Optional[int]  # target id
    lineno: t.Optional[int]

    # protected attribute
    _id: int = 0

    def __init__(
        self,
        opcode: int,
        arg: int
    ) -> None:
        self.id = _Instruction._id
        self.opcode = opcode
        self.arg = arg

        self.jump_target = None
        self.lineno = None

        _Instruction._id += 1

    def __repr__(self) -> str:
        return ("Instruction("
                f"id={self.id}, "
                f"opcode={self.opcode}, "
                f"opname={dis.opname[self.opcode]}, "
                f"arg={self.arg}"
                ")")

    @classmethod
    def create(cls, ins: dis.Instruction) -> '_Instruction':
        return cls(
            ins.opcode,
            ins.arg or 0
        )


@dataclass
class _Goto:
    target: int
    ins: _Instruction
    block: t.Sequence[int]


@dataclass
class _Label:
    ins: _Instruction
    block: t.Sequence[int]


F = t.TypeVar("F", bound=t.Callable[..., t.Any])


def with_goto(func: F) -> F:
    func.__code__ = patch(func.__code__)
    return func


def patch(code: types.CodeType) -> types.CodeType:
    co_consts = list(code.co_consts)
    instructions = list(_get_instructions(code))
    gotos, labels = _find_statements(code, instructions)

    # remove labels and fix its referrer
    for label in labels.values():
        index, ins = _find_by_id(instructions, label.ins.id)
        assert ins is not None
        # delete LOAD_GLOBAL label, LOAD_ATTR, POP_TOP
        del instructions[index:index + 3]

        jump_referrer = filter(lambda x: x.jump_target == ins.id, instructions)
        for referrer_ins in jump_referrer:
            referrer_ins.jump_target = instructions[index].id

        label.ins = instructions[index]

    # remove gotos and refer to its target/label
    for goto in gotos:
        index, _ = _find_by_id(instructions, goto.ins.id)
        # delete LOAD_ATTR, POP_TOP
        del instructions[index + 1:index + (1 + 2)]

        target_label = labels.get(goto.target, None)
        if target_label is None:
            raise SyntaxError(f"label {code.co_names[goto.target]!r} not defined in this function."
                              f" at line {_take_min_lineno(instructions, index)}")

        _, jump_target_ins = _find_by_id(instructions, target_label.ins.id)

        goto.ins.opcode = dis.opmap["JUMP_ABSOLUTE"]
        goto.ins.jump_target = jump_target_ins.id

        # implicit push/pop block
        ins = None
        for ins in _get_block_ins(instructions, co_consts, goto.block, target_label.block, index):
            instructions.insert(index, ins)
        if ins is not None:
            # shift lineno
            instructions[index].lineno, goto.ins.lineno = goto.ins.lineno, None

    return code.replace(
        co_code=bytes(_compile(instructions)),
        co_lnotab=bytes(_compress_lineno(code.co_firstlineno, instructions)),
        co_consts=tuple(co_consts)
    )


def _compile(instructions: t.MutableSequence[_Instruction]) -> t.Generator[int, None, None]:
    """compile sequence of instructions to bytes"""
    # extending args must be done right before compilation
    _extend_args(instructions)
    for i, ins in enumerate(instructions):
        arg = ins.arg
        if ins.opcode in dis.hasjabs:
            target_i, _ = _find_by_id(instructions, ins.jump_target)
            assert target_i != -1
            arg = _get_offset(target_i)
        elif ins.opcode in dis.hasjrel:
            target_i, _ = _find_by_id(instructions, ins.jump_target)
            assert target_i != -1
            target_offset, curr_offset = _get_offset(target_i), _get_offset(i)
            arg = max(target_offset, curr_offset) - 2 - min(target_offset, curr_offset)

        if arg >= 256:
            (arg, _), *_ = _split_arg(arg)

        yield from (ins.opcode, arg)


def _extend_args(instructions: t.MutableSequence[_Instruction]) -> None:
    """
    extend the argument of every instructions that is greater than 255.
    see https://docs.python.org/3/library/dis.html#opcode-EXTENDED_ARG
    """
    for i, ins in (it := enumerate(instructions)):
        arg = ins.arg
        if ins.opcode in dis.hasjabs:
            target_i, _ = _find_by_id(instructions, ins.jump_target)
            assert target_i != -1
            arg = _get_offset(target_i)
        elif ins.opcode in dis.hasjrel:
            target_i, _ = _find_by_id(instructions, ins.jump_target)
            assert target_i != -1
            target_offset, curr_offset = _get_offset(target_i), _get_offset(i)
            arg = max(target_offset, curr_offset) - 2 - min(target_offset, curr_offset)

        if arg >= 256:
            for _, extended_argv in _split_arg(arg):
                instructions.insert(i, _Instruction(dis.opmap["EXTENDED_ARG"], extended_argv))
                next(it)
            last_extended_arg = instructions[i]  # most top EXTENDED_ARG

            jump_referrer = filter(lambda x: x.jump_target == ins.id, instructions)
            for referrer_ins in jump_referrer:
                referrer_ins.jump_target = last_extended_arg.id

            # shift lineno
            last_extended_arg.lineno, ins.lineno = ins.lineno, None


def _get_block_ins(
    instructions: t.Sequence[_Instruction],
    co_consts: t.MutableSequence[t.Any],
    origin: t.Sequence[int],
    target: t.Sequence[int],
    origin_i: int  # for better error message
) -> t.Generator[_Instruction, None, None]:
    """calculate what instructions are needed to exit/enter a block correctly"""
    if len(origin) > len(target):
        # exit block / goto outer scope
        if origin[:len(target)] != target:
            raise SyntaxError("jump into different block."
                              f" at line {_take_min_lineno(instructions, origin_i)}")

        for ins_id in reversed(origin[len(target):]):
            _, ins = _find_by_id(instructions, ins_id)
            assert ins is not None
            opname = dis.opname[ins.opcode]
            if opname == "SETUP_FINALLY":
                yield _Instruction(dis.opmap["POP_BLOCK"], 0)
            elif opname == "SETUP_WITH":
                if None not in co_consts:
                    co_consts.append(None)
                yield from reversed((
                    _Instruction(dis.opmap["POP_BLOCK"], 0),
                    _Instruction(dis.opmap["LOAD_CONST"], co_consts.index(None)),
                    _Instruction(dis.opmap["DUP_TOP"], 0),
                    _Instruction(dis.opmap["DUP_TOP"], 0),
                    _Instruction(dis.opmap["CALL_FUNCTION"], 3),
                    _Instruction(dis.opmap["POP_TOP"], 0)
                ))
            elif opname == "SETUP_ASYNC_WITH":
                if None not in co_consts:
                    co_consts.append(None)
                none_i = co_consts.index(None)
                yield from reversed((
                    _Instruction(dis.opmap["POP_BLOCK"], 0),
                    _Instruction(dis.opmap["LOAD_CONST"], none_i),
                    _Instruction(dis.opmap["DUP_TOP"], 0),
                    _Instruction(dis.opmap["DUP_TOP"], 0),
                    _Instruction(dis.opmap["CALL_FUNCTION"], 3),
                    _Instruction(dis.opmap["GET_AWAITABLE"], 0),
                    _Instruction(dis.opmap["LOAD_CONST"], none_i),
                    _Instruction(dis.opmap["YIELD_FROM"], 0),
                    _Instruction(dis.opmap["POP_TOP"], 0)
                ))
            elif opname == "FOR_ITER":
                yield _Instruction(dis.opmap["POP_TOP"], 0)
            else:
                assert False, f"not a jump instruction: {opname}"
    elif len(origin) < len(target):
        # enter block / goto inner scope
        if target[:len(origin)] != origin:
            raise SyntaxError("jump into different block."
                              f" at line {_take_min_lineno(instructions, origin_i)}")

        for ins_id in target[len(origin):]:
            _, ins = _find_by_id(instructions, ins_id)
            assert ins is not None
            opname = dis.opname[ins.opcode]
            if opname == "SETUP_FINALLY":
                ins_copy = _Instruction(ins.opcode, ins.arg)
                ins_copy.jump_target = ins.jump_target
                yield ins_copy
            elif opname in ("SETUP_WITH", "SETUP_ASYNC_WITH",
                            "FOR_ITER"):
                raise SyntaxError("can't jump into 'with' or 'for' block."
                                  f" at line {_take_min_lineno(instructions, origin_i)}")
            else:
                assert False, f"not a jump instruction: {opname}"
    elif origin == target:
        # on the same block / normal goto
        pass
    else:
        raise SyntaxError("jump into different block."
                          f" at line {_take_min_lineno(instructions, origin_i)}")


def _split_arg(value: int) -> t.Generator[t.Tuple[int, int], None, None]:
    """
    split `value` to three extended_arg argument.
    see https://docs.python.org/3/library/dis.html#opcode-EXTENDED_ARG

    EXTENDED_ARG 1
    JUMP_ABSOLUTE 23

    the first yield value is the remainder value, used in JUMP_ABSOLUTE, and will remain the same.
    the second yield value is extended extended argument, used in EXTENDED_ARG.
    """
    first, value = divmod(value, 256)
    second, first = divmod(first, 256)
    last, second = divmod(second, 256)
    if last >= 256:
        raise ValueError(f"too big numbers, max is 32 bit")

    if last:
        yield value, last
    if second:
        yield value, second
    if first:
        yield value, first


def _compress_lineno(
    firstlineno: int,
    instructions: t.Iterable[_Instruction]
) -> t.Generator[int, None, None]:
    """compress line number to line number table (co_lnotab)"""
    prevoffset = 0
    prevline = firstlineno
    for i, ins in filter(lambda x: x[1].lineno is not None, enumerate(instructions)):
        # range offset, range line
        roffset, rline = _get_offset(i)-prevoffset, ins.lineno-prevline

        if roffset >= 256:
            # send a PR if you know a more suitable name for 'div' and 'mod'
            div, mod = divmod(roffset, 255)
            yield from (255, 0) * div
            yield from (mod, 0)
            if rline < 256:
                yield from (0, rline)
        if rline >= 256:
            div, mod = divmod(rline, 255)
            yield from (255, 0) * div
            yield from (mod, 0)
            if roffset < 256:
                yield from (roffset, 0)
        if roffset < 256 > rline:
            yield from (roffset, rline)

        prevoffset, prevline = _get_offset(i), ins.lineno


def _find_statements(
    code: types.CodeType,
    instructions: t.Sequence[_Instruction]
) -> t.Tuple[t.Sequence[_Goto], t.Dict[int, _Label]]:
    """find gotos and labels"""
    gotos: t.List[_Goto] = []
    labels: t.Dict[int, _Label] = {}

    for_end: t.Set[int] = set()  # end FOR_ITER id
    block_stack: t.List[int] = []  # block start id
    for i, ins in enumerate(instructions):
        if ins.id in for_end:
            for_end.remove(ins.id)
            if block_stack:
                block_stack.pop()

        opname = dis.opname[ins.opcode]
        if opname in ("LOAD_GLOBAL", "LOAD_NAME"):
            load_attr, pop_top = instructions[i + 1], instructions[i + 2]
            if not (dis.opname[load_attr.opcode] == "LOAD_ATTR" and
                    dis.opname[pop_top.opcode] == "POP_TOP"):
                continue

            if code.co_names[ins.arg] == "goto":
                gotos.append(_Goto(load_attr.arg, ins, tuple(block_stack)))
            elif code.co_names[ins.arg] == "label":
                if load_attr.arg in labels:
                    raise SyntaxError(f"ambiguous label name: {code.co_names[load_attr.arg]!r}."
                                      f" at line {_take_min_lineno(instructions, i)}")

                labels[load_attr.arg] = _Label(ins, tuple(block_stack))
        elif opname in ("SETUP_FINALLY", "SETUP_WITH",
                        "SETUP_ASYNC_WITH", "FOR_ITER"):
            block_stack.append(ins.id)
            if opname == "FOR_ITER":
                for_end.add(ins.jump_target)
        elif opname == "POP_BLOCK" and block_stack:
            block_stack.pop()

    return gotos, labels


def _get_instructions(code: types.CodeType) -> t.Generator[_Instruction, None, None]:
    instructions = list(map(_Instruction.create, dis.get_instructions(code)))
    linemap = dict(dis.findlinestarts(code))

    for i, ins in enumerate(instructions):
        if ins.opcode in dis.hasjabs:
            jump_target_ins = None
            for jump_target_ins in instructions[_get_index(ins.arg):]:
                if dis.opname[jump_target_ins.opcode] != "EXTENDED_ARG":
                    break
            assert jump_target_ins is not None
            ins.jump_target = jump_target_ins.id
        elif ins.opcode in dis.hasjrel:
            jump_target_ins = None
            for jump_target_ins in instructions[_get_index(_get_offset(i) + 2 + ins.arg):]:
                if dis.opname[jump_target_ins.opcode] != "EXTENDED_ARG":
                    break
            assert jump_target_ins is not None
            ins.jump_target = jump_target_ins.id
        elif dis.opname[ins.opcode] == "EXTENDED_ARG":
            offset = _get_offset(i)
            if (lineno := linemap.get(offset, None)) is not None:
                linemap[offset + 2] = lineno
                del linemap[offset]
            continue

        if (lineno := linemap.get(_get_offset(i), None)) is not None:
            ins.lineno = lineno

        yield ins


def _take_min_lineno(instructions: t.Sequence[_Instruction], index: int) -> int:
    if (lineno := instructions[index].lineno) is not None:
        return lineno

    for ins in reversed(instructions[:index]):
        if ins.lineno is not None:
            return ins.lineno
    assert False, "is not working"


def _get_offset(x: int) -> int:
    """
    get offset from index. this function is intended to make it more clear.
    just multiply by 2 since python 3.6 and above always uses 2 bytes for each instructions
    """
    return x * 2


def _get_index(x: int) -> int:
    """
    get index from offset. this function is intended to make it more clear.
    just divide by 2 since python 3.6 and above always uses 2 bytes for each instructions
    """
    return x // 2


def _find_by_id(instructions: t.Iterable[_Instruction], id: int) -> t.Tuple[int, t.Optional[_Instruction]]:
    """find instruction by its id, returns the index and instruction"""
    for i, ins in enumerate(instructions):
        if ins.id == id:
            return i, ins

    return -1, None
