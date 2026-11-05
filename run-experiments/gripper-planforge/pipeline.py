import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile

from translate import HERE, translate

DEFAULT_ENGINE = HERE.parents[2] / 'PlanForge/target/release/planforge'
CSV_COLUMNS = {
    'states.csv': {'state_id', 'is_goal', 'h_star'},
    'transitions.csv': {'source_state_id', 'operator_id', 'successor_state_id', 'cost'},
    'summary.csv': {'metric', 'value'},
    'h_star_histogram.csv': {'h_star', 'state_count'},
}


def load_config(path):
    with Path(path).open(encoding='utf-8-sig') as handle:
        config = json.load(handle)['planforge']
    for key in ('max_states', 'max_transitions'):
        if type(config.get(key)) is not int or config[key] <= 0:
            raise ValueError(f'{key} must be a positive integer')
    if not isinstance(config.get('max_time'), str) or not config['max_time'].strip():
        raise ValueError('max_time must be a non-empty duration, for example 30s')
    return config


def validate_export(directory):

    tables = {}
    for name, required in CSV_COLUMNS.items():
        with (Path(directory) / name).open(newline='', encoding='utf-8') as handle:
            reader = csv.DictReader(handle)
            if not required <= set(reader.fieldnames or []):
                raise ValueError(f'Invalid CSV header: {name}')
            tables[name] = list(reader)
    states = tables['states.csv']
    edges = tables['transitions.csv']
    ids = {int(row['state_id']) for row in states}
    if not states or len(ids) != len(states) or 0 not in ids:
        raise ValueError('State IDs must be unique and include initial state 0')
    if any(row['is_goal'] not in ('true', 'false') for row in states):
        raise ValueError('Invalid goal flag')
    for row in edges:
        if int(row['source_state_id']) not in ids or int(row['successor_state_id']) not in ids:
            raise ValueError('Transition references an unknown state')
    summary = {row['metric']: row['value'] for row in tables['summary.csv']}
    for key, actual in (('states', len(states)), ('transitions', len(edges)),
                        ('goal_states', sum(row['is_goal'] == 'true' for row in states))):
        if int(summary[key]) != actual:
            raise ValueError(f'Summary does not match exported rows: {key}')
    if sum(int(row['state_count']) for row in tables['h_star_histogram.csv']) != len(states):
        raise ValueError('Histogram does not account for all states')
    return tables


def enumerate_sas(sas, directory, config):

    engine = Path(os.environ.get('PLANFORGE_BIN', DEFAULT_ENGINE)).expanduser().resolve()
    if not engine.is_file():
        raise FileNotFoundError(f'Missing PlanForge binary: {engine}; build --bin planforge')
    subprocess.run([
        str(engine), 'enumerate', '--max-states', str(config['max_states']),
        '--max-transitions', str(config['max_transitions']), '--max-time', config['max_time'],
        '--output', str(Path(directory).resolve()), str(Path(sas).resolve()),
    ], check=True)
    return validate_export(directory)


def prepare(domain, problem, output, config):

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    destinations = [output / 'gripper.sas', output / 'enumeration']
    if any(Path(source).resolve().is_relative_to(target)
           for source in (domain, problem) for target in destinations):
        raise ValueError('Generated output must not overwrite a PDDL input')
    with tempfile.TemporaryDirectory(prefix='prepare-', dir=output) as tmp:
        staged = Path(tmp)
        translate(domain, problem, staged / 'gripper.sas')
        enumerate_sas(staged / 'gripper.sas', staged / 'enumeration', config)
        # Keep backups until both entries have been published; restore if it fails
        backups, published = [], []
        try:
            for target in destinations:
                if target.exists() or target.is_symlink():
                    backup = staged / (target.name + '.previous')
                    target.rename(backup)
                    backups.append((target, backup))
                (staged / target.name).rename(target)
                published.append(target)
        except OSError:
            for target in reversed(published):
                target.rename(staged / target.name)
            for target, backup in reversed(backups):
                backup.rename(target)
            raise
    print(f'Prepared SAS+ and enumeration: {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('translate', 'prepare'))
    parser.add_argument('--domain', type=Path, default=HERE / 'pddl/domain.pddl')
    parser.add_argument('--problem', type=Path, default=HERE / 'pddl/problem-2balls.pddl')
    parser.add_argument('--output-dir', type=Path, default=HERE / 'output')
    parser.add_argument('--config', type=Path, default=HERE / 'params.json')
    args = parser.parse_args()
    if args.command == 'translate':
        print(f'SAS+ file: {translate(args.domain, args.problem, args.output_dir / "gripper.sas")}')
    else:
        prepare(args.domain, args.problem, args.output_dir, load_config(args.config))


if __name__ == '__main__':
    main()
