# AutoResearch CLI

## Warning! Not working for now. Just AI slop. Give me couple weeks please:)

CLI tool to manage LLM-driven research experiments. Works alongside [Karpathy's AutoResearch](https://github.com/karpathy/autoresearch) pattern.

## Installation

```bash
uv tool install -e git+https://github.com/igorjakus/autoresearch-cli
```

Or from local:

```bash
uv tool install -e .
```

## Usage

```bash
autoresearch init --metric loss --direction lower --baseline 2.5 \
  --quick-duration 5 --deep-duration 30 \
  --quick-run "just pretrain --time-budget 5" \
  --deep-run "just pretrain --time-budget 30" \
  --editable-files "src/config.py,src/model.py"

autoresearch idea add "Try Muon optimizer"
autoresearch idea pop
autoresearch result 2.4 8.0 5 "tried Muon"
autoresearch result-deep 2.35 8.5 30 "Muon verified"
autoresearch reject
autoresearch log
autoresearch status
autoresearch prompt
autoresearch verify
```

## Commands

- `autoresearch init` - Initialize autoresearch in current directory
- `autoresearch idea add "text"` - Add idea to queue
- `autoresearch idea pop` - Get next idea
- `autoresearch idea list` - List all ideas
- `autoresearch result <val> <mem> <time> <desc>` - Record quick experiment result
- `autoresearch result-deep <val> <mem> <time> <desc>` - Record deep experiment result
- `autoresearch reject` - Reject insignificant improvement
- `autoresearch log` - Show experiment history
- `autoresearch status` - Show current status
- `autoresearch prompt` - Print program.md
- `autoresearch verify` - Check only editable files changed
