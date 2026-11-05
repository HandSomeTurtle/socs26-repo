from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Variable:
    name: str
    facts: tuple[str, ...]


@dataclass(frozen=True)
class Task:
    variables: tuple[Variable, ...]
    initial_values: tuple[int, ...]
    operators: tuple[str, ...]


def _blocks(lines, start_marker, end_marker):
    blocks = []
    i = 0
    while i < len(lines):
        if lines[i] != start_marker:
            i += 1
            continue
        j = i + 1
        while j < len(lines) and lines[j] != end_marker:
            j += 1
        if j == len(lines):
            raise ValueError(f"Missing {end_marker} after line {i + 1}")
        blocks.append(lines[i + 1:j])
        i = j + 1
    return blocks


def read_sas(path):
    lines = [line.strip() for line in Path(path).read_text(encoding='utf-8').splitlines()]
    variables = []
    for block in _blocks(lines, 'begin_variable', 'end_variable'):
        if len(block) < 3:
            raise ValueError('Invalid begin_variable block')
        size = int(block[2]); facts = tuple(block[3:])
        if len(facts) != size:
            raise ValueError(f"Variable {block[0]}: {len(facts)} facts, expected {size}")
        variables.append(Variable(block[0], facts))
    state_blocks = _blocks(lines, 'begin_state', 'end_state')
    if len(state_blocks) != 1:
        raise ValueError(f"Expected one begin_state block instead found: {len(state_blocks)}")
    initial = tuple(map(int, state_blocks[0]))
    if len(initial) != len(variables):
        raise ValueError('SAS+ initial state incorrect length')
    operators = tuple(block[0] for block in _blocks(lines, 'begin_operator', 'end_operator'))
    if not variables or not operators:
        raise ValueError('No SAS+ variables/operators found')
    for var, value in zip(variables, initial):
        if not 0 <= value < len(var.facts):
            raise ValueError(f"Invalid initial value {value} for {var.name}")
    return Task(tuple(variables), initial, operators)
