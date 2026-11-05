"""Integration tests using the real PlanForge translator."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from translate import translate
from sas_reader import read_sas


class TranslationTest(unittest.TestCase):
    def test_gripper_translation(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'gripper.sas'
            translate(HERE / 'pddl/domain.pddl', HERE / 'pddl/problem-2balls.pddl', output)
            task = read_sas(output)
            expected = {'move rooma roomb', 'move roomb rooma'}
            expected.update(f'{action} {ball} {room} {gripper}'
                            for action in ('pick', 'drop')
                            for ball in ('ball1', 'ball2')
                            for room in ('rooma', 'roomb')
                            for gripper in ('left', 'right'))
            self.assertEqual(set(task.operators), expected)
            self.assertEqual(len(task.operators), 18)
            initial = {var.facts[value] for var, value in
                       zip(task.variables, task.initial_values)}
            self.assertTrue({'Atom at-robby(rooma)', 'Atom at(ball1, rooma)',
                             'Atom at(ball2, rooma)', 'Atom free(left)',
                             'Atom free(right)'} <= initial)
            text = output.read_text(encoding='utf-8')
            self.assertIn('begin_goal\n', text)
            self.assertIn('end_goal\n', text)

    def test_invalid_pddl_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / 'invalid.pddl'
            bad.write_text('this is not PDDL', encoding='utf-8')
            output = Path(tmp) / 'gripper.sas'
            output.write_text('previous output', encoding='utf-8')
            with self.assertRaises(subprocess.CalledProcessError):
                translate(HERE / 'pddl/domain.pddl', bad, output)
            self.assertEqual(output.read_text(encoding='utf-8'), 'previous output')


if __name__ == '__main__':
    unittest.main(verbosity=2)
