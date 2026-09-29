# Notes for ggml-org/llama.cpp#28963 (facts only, write the posts yourself)

## Before you post: llama.cpp rules

- CONTRIBUTING: the PR description, issue comments and review replies must be written by you. Using AI to write them is not allowed. Do not paste anything from this file; it is a list of facts.
- You must disclose that AI helped write the code/investigation. Undisclosed AI use can get you banned.
- New contributors may have only one open PR.
- You are responsible for every line of the patch, so be ready to explain it (see TALKING-POINTS.md).

## Status checked (2026-09-28)

- #28963 was open, labelled `bug-unconfirmed`, with no assignee, no comments and no linked PR. A PR search for "28963" returned 0 results.
- #29121 (in-place GDN state on CPU) does not touch this bug. The GDN layers are the ones that do *not* diverge.
- #29313 / #29370 (stale gallocr plan when OUTPUT flags change) is unrelated. The allocator is not involved here.
- Re-check just before opening the PR in case someone else has picked it up.

## Root cause

- For an embedding batch on an M-RoPE model, `llama_decode()` reads `n_tokens * 4` entries from `llama_batch.pos`, laid out section-major as `pos[j*n_tokens + i]`, j = 0..3.
  - Code at HEAD 1c47294: `src/llama-batch.cpp:1286`, `llama_batch_compat::init`: `t.pos[j] = batch_inp.pos[(int32_t) j * batch_inp.n_tokens + i];`
  - Code at the reporter's commit 6f04274: `src/llama-batch.cpp:786-787`, `llama_batch_allocr::ubatch_add`: `src_off = batch.token ? 0 : j*batch.n_tokens`
  - 4 = `n_pos_per_embd()` for `LLAMA_ROPE_TYPE_MROPE` / `IMROPE` (`src/llama-hparams.cpp:285`). Qwen3.5 uses IMROPE, so it gets 4.
- `llama_batch_init(n, embd, ...)` allocates `pos` with only `n` entries (`src/llama-batch.cpp:997`), and the header says every array is `n_tokens` long (`include/llama.h:249`).
- Result: a caller that uses `llama_batch_init` and sets `pos[i]` exactly as for a token batch makes decode read `3*n_tokens` ints past the end of a heap block. Those values end up as the sections 1..3 positions in `inp_pos`.
- Token batches do not have the problem. For them, `llm_graph_input_pos::set_input` builds `(p,p,p,0)` from the single position (`src/llama-graph.cpp:131`).

## Why it shows up as the reported symptoms

- Positions are used only by ROPE in the full-attention layers. The gated-delta-net (linear attention) layers do not use them.
  - So layers before the first full-attention layer match bitwise, and the first difference is at `ROPE(Qcur_normed-L, inp_pos)`.
  - For Qwen3.5-2B/0.8B (full attention every 4th layer) that is layer 3, which matches the report.
- 1-token batch: attention over a single key gives softmax = 1, so the output is V whatever the rotation. That makes it deterministic even with garbage positions.
- All-zero input: RMS norm of zero is zero, so q and k are zero and the rotation has no effect. Also deterministic.
- "A small set of recurring states": the garbage is whatever the allocator left in neighbouring chunks, and that has only a few patterns.
- Argmax is stable: only rotary angles in some sections change, the embeddings are the same.
- Threads, KV cache, flash attention and fused ops are all downstream of `inp_pos`, so ruling them out could not have found this.

## Evidence (files in repro/)

- `repro/embd-determinism.cpp`: decodes the same batch N times with memory cleared each time and FNV-hashes all logits. `pos_mode` is `n` (llama_batch_init, sets pos[i]), `full` (a 4*n section-major array) or `null`.
- Real model: ggml-org/Qwen3.5-0.8B-GGUF Q8_0, CPU, n_ctx = n_batch = n_ubatch = 512.
  - Before: `embd 5 tokens pos=n` gave 6 distinct hashes out of 6 runs. Token path: 1/6. `embd 1 token`: 1/6. `pos=full`: 1/6. See `before-qwen3.5-0.8b.txt`.
  - After: `embd 5 pos=n` gives 1 distinct hash out of 6. See `after-qwen3.5-0.8b.txt`.
- Tiny random qwen35 model, generated with `test-llama-archs -a qwen35 -s 42 -o DIR` (about 5 MB, full attention every 2nd layer):
  - Before: `embd 5 pos=n` gave 8 distinct hashes out of 8 runs, 4 threads and 1 thread alike (`before-tiny-qwen35.txt`).
  - After: 1/8 in every mode (`after-tiny-qwen35.txt`).
- `repro/first-divergence.cpp`: uses `cb_eval` to capture every tensor in two decodes and prints `inp_pos` plus the first tensor that differs.
  - Before, tiny model: `inp_pos` sections 1..3 hold garbage such as `16448 49 0 1788850096 21910 ...` and `1077952576`. 1077952576 is 0x40404040, the byte pattern the program wrote into freed heap memory, so the values are shown to come from the heap.
  - First differing tensor is `Qcur-1 = ROPE(Qcur_normed-1, inp_pos)`. Everything before it matches bitwise.
  - After: `inp_pos` sections 1..3 are all 0, and all 131 evaluated tensors match bitwise.
  - 0.8B model before: first differing tensor `Qcur-3 = ROPE(Qcur_normed-3, inp_pos)`, the first full-attention layer, exactly as the issue reports. After: `inp_pos` sections 1..3 are 0 and all 1423 evaluated tensors match bitwise.
  - Side note: `node_0 = GET_ROWS(token_embd, inp_tokens)` also "differs". That is the unselected branch of `ggml_build_forward_select`. It is not computed (no COMPUTE flag), so the callback just sees an unwritten buffer. It is not the bug.
- Valgrind memcheck on `test-batch-alloc` with the new test:
  - Before: `Invalid read of size 4 at llama_batch_compat::init (llama-batch.cpp:1286) ... 0 bytes after a block of size 12 alloc'd`, `ERROR SUMMARY: 9 errors`.
  - After: 0 errors (`*-valgrind-test-batch-alloc.txt`).
- Reporter-commit specifics (6f04274, before `llama_batch_ext` #24669 landed on 2026-09-24):
  - `pos == NULL` embd batches were also out of bounds there: `pos.resize(batch.n_tokens)` at :91, then read at `j*n_tokens` at :787, inside a std::vector.
  - That variant is already fixed at HEAD, because `llama_batch_compat::init` zero-fills `t.pos[1..3]`. Verified: `pos=null` is deterministic at HEAD before the patch.
  - The explicit-`pos` variant still reproduces at HEAD.
  - We do not know which variant the reporter's probe used. Ask them, or ask them to retest on HEAD with the patch.

## The fix (fix.patch, 3 files, +45/-2)

- `src/llama-batch.cpp` `llama_batch_init`: when `embd != 0`, allocate `pos` with `n_tokens_alloc * GGML_MROPE_SECTIONS` entries using `calloc` (zeroed). Token batches keep the `malloc(n)` allocation as before.
  - Every index decode can read (up to `3*n_tokens + n_tokens - 1` for any `n_tokens <= n_tokens_alloc`) is now inside the allocation.
  - Sections the caller did not set read as 0, so results are deterministic.
- `include/llama.h`: documents that embd batches on MROPE/IMROPE models need `4*n_tokens` positions in section-major order, and that `llama_batch_init` sizes and zeroes `pos` for that.
- Design choice: the documented 4-row convention is kept. `tests/test-batch-alloc.cpp: embd_batch_with_mrope_positions` locks it in, and external code that copied the old mtmd `decode_embd_batch` depends on it.
- Semantic caveat, which maintainers may raise:
  - With only `pos[i]` set, the M-RoPE positions after the fix are `(p,0,0,0)`, not the token path's `(p,p,p,0)`.
  - Verified on the tiny model: `pos=n` after the fix gives the same hash as `pos=null` (`e803a398...`). `pos=full` with `(p,p,p,0)` gives a different hash (`81e098e7...`).
  - Callers who want token-equivalent RoPE must pass all 4 rows, or use `llama_batch_ext_set_pos`.
- Not fixed: a caller that passes its own n-sized `pos` array (not from `llama_batch_init`) still over-reads. The legacy `llama_batch` has no field for the array length, so the library cannot detect this. The header comment is the only mitigation.
- Alternatives a maintainer might prefer (worth mentioning as options, not claims):
  - (a) Read only `n_tokens` positions in the compat path and broadcast `(p,p,p,0)`. This breaks existing 4-row callers.
  - (b) Deprecate legacy embd batches on M-RoPE in favour of `llama_batch_ext`.
- No ggml ops changed, so test-backend-ops is not relevant. There are no graph or allocator changes.

## Tests

- New test: `tests/test-batch-alloc.cpp` -> `test_compat` -> `embd_batch_init_mrope_pos_in_bounds`.
  - Builds an embd batch with `llama_batch_init(3, 2, 1)`, sets only `pos[i]`, runs `llama_batch_compat::init` with n_pos=4, and asserts pos[0]=10+i and pos[1..3]=0.
  - Already wired: `llama_build_and_test(test-batch-alloc.cpp)`, ctest name `test-batch-alloc`. No model needed.
  - Before the fix: 6 of 340 assertions fail, with heap garbage such as 33 and 1, and valgrind reports an invalid read. After: 0 failures, and valgrind is clean.
- Also run after the fix: `ctest -R test-batch-alloc` passed. `test-save-load-state --models <dir with generated qwen35-dense.gguf>` passed all 9 columns. That test uses `llama_batch_init(n, embd, ...)`.
- Build: `cmake -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo -DLLAMA_CURL=OFF` on Linux x86-64, CPU only.
- Not run: the full ctest suite, sanitizer builds (valgrind was used instead), and Windows (the reporter's platform).

## Commit

- One commit on local branch `fix-28963-embd-mrope-pos` in `/home/user/oss3/llama.cpp`, authored `Azra Bano <azrabano.work@gmail.com>`, with no AI trailer. The AI-assistance disclosure goes in your PR text.
- `fix.patch` is `git format-patch` output of that commit.
