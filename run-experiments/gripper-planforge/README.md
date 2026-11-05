## Instructions for building and running 

```bash
cd /home/Max/FNN_Gripper
cargo build --release --locked --manifest-path PlanForge/Cargo.toml -p planforge --bin planforge-translator --bin planforge
cd socs26-repo/run-experiments/gripper-planforge

# Translation only:
python3 pipeline.py translate

# Translation followed by enumeration:
python3 pipeline.py prepare

# Run all six tests:
python3 -m unittest discover -s checks -p 'test_*.py' -v
```

```bash
python3 pipeline.py prepare \
  --domain pddl/domain.pddl \
  --problem pddl/problem-2balls.pddl \
  --config params.json \
  --output-dir output
```

## Configuration and executable paths

```json
{
  "planforge": {
    "max_states": 1000,
    "max_transitions": 10000,
    "max_time": "30s"
  }
}
```

## Tests and expected values

1. PDDL translation: 18 grounded operators, expected initial facts and SAS blocks.
2. Invalid PDDL: the translator fails and preserves a previous output.
3. Real `prepare` CLI from an unrelated working directory, followed by a repeat run.
4. Real state-limit failure (`max_states=1`): previous SAS+ and enumeration survive.
5. Simulated enumeration failure: previous results survive and staging is cleaned up.
6. Simulated publication failure: previous results are restored.

The graph test expects: 28 states
                        76 directed edges
                        two goals
                        initial h*=5