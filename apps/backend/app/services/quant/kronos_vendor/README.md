# Vendored: Kronos

`model/` (`kronos.py`, `module.py`, `__init__.py`) is vendored verbatim,
unmodified, from:

https://github.com/shiyu-coder/Kronos (commit at time of vendoring: 2026-08-16)

"Kronos: A Foundation Model for the Language of Financial Markets"
(arXiv:2508.02739, AAAI 2026) — a decoder-only foundation model
pre-trained on K-line (OHLCV) sequences from 45 global exchanges.

MIT License — see `LICENSE` in this folder (the original repo's license,
copied alongside the code it covers).

Only the `model/` package is vendored — `examples/`, `finetune/`,
`finetune_csv/`, and `webui/` from the upstream repo are intentionally
NOT included. Phase 2C is explicitly pretrained-inference-only (owner
instruction: "run the released pretrained model first... don't
fine-tune yet") — vendoring the fine-tuning pipeline would be dead code
inviting accidental use.

Do not hand-edit files in `model/` — if the upstream model changes,
re-vendor from the source repo rather than patching a fork in place.

Pretrained weights are NOT vendored here — `kronos_model.py` (the
wrapper one level up) downloads them from Hugging Face Hub
(`NeoQuasar/Kronos-Tokenizer-base`, `NeoQuasar/Kronos-small`) at first
use, cached locally by `huggingface_hub`'s own cache mechanism.
