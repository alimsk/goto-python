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


def patch(code: types.CodeType) -> types.CodeType:
    co_consts = list(code.co_consts)
    instructions = list(_get_instructions(code))
    gotos, labels = _find_goto_and_label(code, instructions)

    # remove labels and fix its referrer
    for label in labels.values():
        index, ins = _find_by_id(instructions, label.ins.id)
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
        _, jump_target_ins = _find_by_id(instructions, labels[goto.target].ins.id)
        goto.ins.opcode = dis.opmap["JUMP_ABSOLUTE"]
        goto.ins.jump_target = jump_target_ins.id

        # implicit push/pop block
        ins = None
        for ins in _get_block_ins(instructions, co_consts, goto.block, labels[goto.target].block):
            instructions.insert(index, ins)
        if ins is not None:
            # shift lineno
            instructions[index].lineno, goto.ins.lineno = goto.ins.lineno, None

    # extended args
    # see https://docs.python.org/3/library/dis.html#opcode-EXTENDED_ARG
    for i, ins in (it := enumerate(instructions)):
        arg = ins.arg
        if ins.opcode in dis.hasjabs:
            target_idx, _ = _find_by_id(instructions, ins.jump_target)
            arg = _get_offset(target_idx)
        elif ins.opcode in dis.hasjrel:
            target_idx, _ = _find_by_id(instructions, ins.jump_target)
            arg = _get_offset(target_idx) - 2 - _get_offset(i)

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

    # compile instructions
    arr = bytearray()
    for i, ins in enumerate(instructions):
        arg = ins.arg
        if ins.opcode in dis.hasjabs:
            target_idx, _ = _find_by_id(instructions, ins.jump_target)
            arg = _get_offset(target_idx)
        elif ins.opcode in dis.hasjrel:
            target_idx, _ = _find_by_id(instructions, ins.jump_target)
            arg = _get_offset(target_idx) - 2 - _get_offset(i)

        if arg >= 256:
            (arg, _), *_ = _split_arg(arg)

        arr.extend((ins.opcode, arg))

    return code.replace(
        co_code=bytes(arr),
        co_lnotab=_compress_lineno(code.co_firstlineno, instructions),
        co_consts=tuple(co_consts)
    )


def _get_block_ins(
    instructions: t.Sequence[_Instruction],
    co_consts: t.MutableSequence[t.Any],
    origin: t.Sequence[int],
    target: t.Sequence[int]
) -> t.Generator[_Instruction, None, None]:
    if len(origin) > len(target):
        # exit block / goto outer scope
        if origin[:len(target)] != target:
            raise SyntaxError("jump into different block")

        for ins_id in reversed(origin[len(target):]):
            _, ins = _find_by_id(instructions, ins_id)
            opname = dis.opname[ins.opcode]
            if opname == "SETUP_FINALLY":
                yield _Instruction(dis.opmap["POP_BLOCK"], 0)
            elif opname in "SETUP_WITH":
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
            raise SyntaxError("jump into different block")

        for ins_id in target[len(origin):]:
            _, ins = _find_by_id(instructions, ins_id)
            opname = dis.opname[ins.opcode]
            if opname == "SETUP_FINALLY":
                ins_copy = _Instruction(ins.opcode, ins.arg)
                ins_copy.jump_target = ins.jump_target
                yield ins_copy
            elif opname in ("SETUP_WITH", "SETUP_ASYNC_WITH",
                            "FOR_ITER"):
                raise SyntaxError("can't jump into 'with' or 'for' block")
            else:
                assert False, f"not a jump instruction: {opname}"
    elif origin == target:
        # on the same block / normal goto
        pass
    else:
        raise SyntaxError("jump into different block")


def _split_arg(value: int) -> t.Generator[t.Tuple[int, int], None, None]:
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


def _compress_lineno(firstlineno: int, instructions: t.Iterable[_Instruction]) -> bytes:
    out = bytearray()

    prevoffset = 0
    prevline = firstlineno
    for i, ins in filter(lambda x: x[1].lineno is not None, enumerate(instructions)):
        # range offset, range line
        roffset, rline = _get_offset(i)-prevoffset, ins.lineno-prevline

        if roffset >= 256:
            # send a PR if you know a more suitable name for 'div' and 'mod'
            div, mod = divmod(roffset, 255)
            out.extend((255, 0) * div)
            out.extend((mod, 0))
            if rline < 256:
                out.extend((0, rline))
        if rline >= 256:
            div, mod = divmod(rline, 255)
            out.extend((255, 0) * div)
            out.extend((mod, 0))
            if roffset < 256:
                out.extend((roffset, 0))
        if roffset < 256 > rline:
            out.extend((roffset, rline))

        prevoffset, prevline = _get_offset(i), ins.lineno

    return bytes(out)


def _find_goto_and_label(
    code: types.CodeType,
    instructions: t.Sequence[_Instruction]
) -> t.Tuple[t.Sequence[_Goto], t.Dict[int, _Label]]:
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
    instructions = tuple(map(_Instruction.create, dis.get_instructions(code)))
    linemap = dict(dis.findlinestarts(code))
    for i, ins in (it := enumerate(instructions)):
        if ins.opcode in dis.hasjabs:
            ins.jump_target = instructions[ins.arg // 2].id
        elif ins.opcode in dis.hasjrel:
            ins.jump_target = instructions[(_get_offset(i) + 2 + ins.arg) // 2].id
        elif dis.opname[ins.opcode] == "EXTENDED_ARG":
            # TODO: support for chained extended_args
            offset = _get_offset(i)
            if (lineno := linemap.get(offset, None)) is not None:
                linemap[offset + 2] = lineno
                del linemap[offset]
            continue

        if (lineno := linemap.get(_get_offset(i), None)) is not None:
            ins.lineno = lineno

        yield ins


def _get_offset(x: int) -> int:
    """get offset from index"""
    return x * 2


def _find_by_id(instructions: t.Iterable[_Instruction], id: int) -> t.Tuple[int, _Instruction]:
    for i, ins in enumerate(instructions):
        if ins.id == id:
            return i, ins

    raise IndexError("instruction id not found")
