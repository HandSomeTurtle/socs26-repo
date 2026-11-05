import argparse
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
DEFAULT_TRANSLATOR = HERE.parents[2] / 'PlanForge/target/release/planforge-translator'

def translate(domain, problem, output):
    translator = Path(os.environ.get('PLANFORGE_TRANSLATOR', DEFAULT_TRANSLATOR)).expanduser().resolve()
    domain, problem, output = (Path(p).resolve() for p in (domain, problem, output))
    for path in (translator, domain, problem):
        if not path.is_file():
            raise FileNotFoundError(f'Missing file: {path}')
    if output in (domain, problem):
        raise ValueError('Output must not overwrite a PDDL input')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Preserve an existing valid output if translation fails.
    with tempfile.TemporaryDirectory(prefix='translate-', dir=output.parent) as tmp:
        staged = Path(tmp) / 'gripper.sas'
        subprocess.run([str(translator), 'translate', str(domain), str(problem),
                        '--output', str(staged)], check=True)
        if not staged.is_file() or staged.stat().st_size == 0:
            raise RuntimeError('Translator didnt produce a non-empty SAS+ file')
        staged.replace(output)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', type=Path, default=HERE / 'pddl/domain.pddl')
    parser.add_argument('--problem', type=Path, default=HERE / 'pddl/problem-2balls.pddl')
    parser.add_argument('--output', type=Path, default=HERE / 'output/gripper.sas')
    args = parser.parse_args()
    print(f'SAS+ file: {translate(args.domain, args.problem, args.output)}')
