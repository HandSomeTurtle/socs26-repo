"""Integration tests for enumeration and graph checks."""
from collections import Counter, deque
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from pipeline import load_config, prepare, validate_export
from sas_reader import _blocks, read_sas


def check_gripper_graph(case, directory, sas):

    tables = validate_export(directory)
    states = {int(row['state_id']): row for row in tables['states.csv']}
    edges = tables['transitions.csv']
    goals = {key for key, row in states.items() if row['is_goal'] == 'true'}
    case.assertEqual(len(states), 28)
    case.assertEqual(len(edges), 76)
    case.assertEqual(len(goals), 2)
    task = read_sas(sas)
    initial = tuple(int(states[0][f'proposition_{i}']) for i in range(len(task.variables)))
    lines = [line.strip() for line in Path(sas).read_text(encoding='utf-8').splitlines()]
    variables = _blocks(lines, 'begin_variable', 'end_variable')
    for index, block in enumerate(variables):
        if int(block[1]) == -1:
            case.assertEqual(initial[index], task.initial_values[index])
    forward = {key: [] for key in states}
    backward = {key: [] for key in states}
    for edge in edges:
        source = int(edge['source_state_id'])
        target = int(edge['successor_state_id'])
        operator = int(edge['operator_id'])
        case.assertTrue(0 <= operator < len(task.operators))
        case.assertEqual(float(edge['cost']), 1.0)
        forward[source].append(target)
        backward[target].append(source)
    reachable, queue = {0}, deque([0])
    while queue:
        for target in forward[queue.popleft()]:
            if target not in reachable:
                reachable.add(target)
                queue.append(target)
    case.assertEqual(reachable, set(states))
    distance, queue = {goal: 0 for goal in goals}, deque(goals)
    while queue:
        target = queue.popleft()
        for source in backward[target]:
            if source not in distance:
                distance[source] = distance[target] + 1
                queue.append(source)
    case.assertEqual(set(distance), set(states), 'Every Gripper state must reach a goal')
    case.assertEqual(distance[0], 5)
    for key, row in states.items():
        case.assertEqual(float(row['h_star']), distance[key])
    histogram = {float(row['h_star']): int(row['state_count'])
                 for row in tables['h_star_histogram.csv']}
    case.assertEqual(histogram, dict(Counter(distance.values())))
    summary = {row['metric']: row['value'] for row in tables['summary.csv']}
    case.assertEqual(int(summary['dead_ends']), 0)


class EnumerationTest(unittest.TestCase):
    def test_prepare_cli_and_repeat_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'result'
            command = [sys.executable, str(HERE / 'pipeline.py'), 'prepare',
                       '--output-dir', str(output)]
            subprocess.run(command, cwd=tmp, check=True)
            check_gripper_graph(self, output / 'enumeration', output / 'gripper.sas')
            subprocess.run(command, cwd=tmp, check=True)
            check_gripper_graph(self, output / 'enumeration', output / 'gripper.sas')

    def test_state_limit_preserves_previous_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'result'
            enumeration = output / 'enumeration'
            enumeration.mkdir(parents=True)
            (output / 'gripper.sas').write_text('previous SAS+', encoding='utf-8')
            marker = enumeration / 'previous.txt'
            marker.write_text('previous enumeration', encoding='utf-8')
            config = load_config(HERE / 'params.json')
            config['max_states'] = 1
            with self.assertRaises(subprocess.CalledProcessError):
                prepare(HERE / 'pddl/domain.pddl', HERE / 'pddl/problem-2balls.pddl',
                        output, config)
            self.assertEqual((output / 'gripper.sas').read_text(encoding='utf-8'), 'previous SAS+')
            self.assertEqual(marker.read_text(encoding='utf-8'), 'previous enumeration')
            self.assertEqual({p.name for p in output.iterdir()}, {'gripper.sas', 'enumeration'})
            self.assertEqual({p.name for p in enumeration.iterdir()}, {'previous.txt'})


class PipelineControlTest(unittest.TestCase):

    def test_failed_enumeration_preserves_both_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / 'result'
            (output / 'enumeration').mkdir(parents=True)
            (output / 'gripper.sas').write_text('old SAS+', encoding='utf-8')
            marker = output / 'enumeration/marker'
            marker.write_text('old graph', encoding='utf-8')

            def fake_translate(domain, problem, destination):
                Path(destination).write_text('new SAS+', encoding='utf-8')

            with patch('pipeline.translate', side_effect=fake_translate), \
                 patch('pipeline.enumerate_sas', side_effect=RuntimeError('enumeration failed')):
                with self.assertRaisesRegex(RuntimeError, 'enumeration failed'):
                    prepare(root / 'domain', root / 'problem', output, {})
            self.assertEqual((output / 'gripper.sas').read_text(), 'old SAS+')
            self.assertEqual(marker.read_text(), 'old graph')
            self.assertEqual({p.name for p in output.iterdir()}, {'gripper.sas', 'enumeration'})

    def test_publication_failure_restores_both_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / 'result'
            (output / 'enumeration').mkdir(parents=True)
            (output / 'gripper.sas').write_text('old SAS+', encoding='utf-8')
            (output / 'enumeration/marker').write_text('old graph', encoding='utf-8')
            original_rename = Path.rename

            def fake_translate(domain, problem, destination):
                Path(destination).write_text('new SAS+', encoding='utf-8')

            def fake_enumerate(sas, destination, config):
                Path(destination).mkdir()

            def fail_new_graph(source, destination):
                if source.name == 'enumeration' and source.parent.name.startswith('prepare-'):
                    raise OSError('simulated publication failure')
                return original_rename(source, destination)

            with patch('pipeline.translate', side_effect=fake_translate), \
                 patch('pipeline.enumerate_sas', side_effect=fake_enumerate), \
                 patch.object(Path, 'rename', fail_new_graph):
                with self.assertRaisesRegex(OSError, 'simulated publication failure'):
                    prepare(root / 'domain', root / 'problem', output, {})
            self.assertEqual((output / 'gripper.sas').read_text(), 'old SAS+')
            self.assertEqual((output / 'enumeration/marker').read_text(), 'old graph')
            self.assertEqual({p.name for p in output.iterdir()}, {'gripper.sas', 'enumeration'})

if __name__ == '__main__':
    unittest.main(verbosity=2)
