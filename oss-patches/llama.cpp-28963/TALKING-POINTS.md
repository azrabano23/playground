# Study guide: llama.cpp #28963 (non-deterministic embd decoding on Qwen3.5)

## 1. How a llama.cpp decode becomes a ggml graph

- `llama_decode(ctx, llama_batch)` goes through several steps:
  - `llama_batch_compat::init` turns the legacy C struct into `llama_batch_ext`, with one `token` record per entry (id, embd offset, seq ids, `pos[4]`).
  - `llama_batch_allocr::init` validates the batch and builds flat arrays. For embd batches, positions are stored section-major.
  - `split_*` produces `llama_ubatch`es.
  - For each ubatch, the model's graph builder (e.g. `src/models/qwen35.cpp`) builds a `ggml_cgraph`.
- Graph inputs are tensors marked with `ggml_set_input` and wrapped in `llm_graph_input_*` objects. Each one has a `set_input(ubatch)` that copies host data into the tensor after allocation. Examples: `inp_tokens`, `inp_embd`, `inp_pos`, KV masks, recurrent state copies.
- `build_inp_embd` creates *both* the token path (`GET_ROWS(tok_embd, inp_tokens)`) and the embd path (`inp_embd`). `ggml_build_forward_select` picks one of them. The branch that is not picked stays in the graph without `GGML_TENSOR_FLAG_COMPUTE`, so the CPU backend skips it. This lets the same graph be reused between token and embd batches.
- `build_inp_pos` creates `inp_pos` as an I32 tensor of `n_tokens * n_pos_per_embd` elements. M-RoPE (`ggml_rope_multi`) reads section `j` of token `i` at `inp_pos[j*n_tokens + i]`.

## 2. Scheduler and allocator (why they were suspects, and why they were cleared)

- `ggml_backend_sched` assigns each node to a backend, splits the graph at backend boundaries, and inserts copies. `ggml_gallocr` (ggml-alloc.c) plans tensor memory: it frees a buffer after its last consumer and reuses it for later nodes.
- The pattern "outputs fall into a small set of recurring states" often points to reused memory being read before it is written. Examples: a stale gallocr plan (#29313), or an input that was never set.
- Here the allocator was fine. The bad data was already in the *host* array that `set_input` copied into `inp_pos`. The scheduler faithfully uploaded garbage.
- How to check: a `cb_eval` callback captures every node output in two runs. Everything matches up to the first `ROPE(..., inp_pos)`, and `inp_pos` itself differs between runs.

## 3. Why embd input differs from token input here

- Token batch on an M-RoPE model: the user gives 1 position per token. `llm_graph_input_pos::set_input` expands it to `(p,p,p,0)`.
- Embd batch on an M-RoPE model: the library assumes the caller gave 4 positions per token (section-major), because vision embeddings need `(t, y, x, z)`. It copies them as they are.
- `llama_batch_init` allocated `pos` with only `n_tokens` entries, and the header says every array has `n_tokens` entries. So a normal caller setting `pos[i]` caused decode to read `3*n_tokens` ints past the end of the heap block.

## 4. How the bug was bisected

1. Reproduced at HEAD with a small program that decodes the same embd batch N times and hashes the logits. 5 tokens gave N distinct hashes. 1 token, the token path, `pos=NULL`, and a full 4-row `pos` were all deterministic. The last result already pointed at positions.
2. Explained the reporter's clues:
   - The first difference is at the first full-attention layer, because only attention layers use RoPE and the GDN layers ignore positions.
   - 1 token is deterministic because softmax over one key is always 1.
   - Zero input is deterministic because the rotation of a zero vector is zero.
3. Read the code path for `pos`: `llama_batch_compat::init` reads `pos[j*n_tokens+i]`, and `llama_batch_init` uses `malloc(n)`.
4. Confirmed with `first-divergence.cpp`, which prints `inp_pos`. Sections 1..3 contained heap garbage, including the 0x40404040 fill pattern the program wrote into freed memory. The first differing tensor was `Qcur-L = ROPE(Qcur_normed-L, inp_pos)`.
5. Confirmed with valgrind memcheck: "Invalid read of size 4 ... 0 bytes after a block of size 12" at `llama-batch.cpp:1286`.
6. Checked history: the reporter's commit predates `llama_batch_ext` (#24669). There, `pos=NULL` was also out of bounds (a std::vector of size n). At HEAD that variant is fixed and only the explicit-`pos` variant remains.

## 5. The fix

- `llama_batch_init`: for embd batches, `calloc(n_tokens_alloc * GGML_MROPE_SECTIONS)` for `pos`. This covers every index decode can read, and positions the caller did not set become 0, so the result is deterministic.
- `llama.h`: documents the 4-row section-major requirement for embd batches on MROPE/IMROPE models, and the new `llama_batch_init` behaviour.
- Regression test in `tests/test-batch-alloc.cpp` (model-free, runs in ctest). Before the fix it fails with garbage values and valgrind flags it. After the fix it passes and valgrind is clean.
- Deliberately *not* changed: the 4-row convention itself. An existing test locks it in, and external callers use it.

## 6. Likely questions and short answers

1. **Why only from the first full-attention layer?** Only full-attention layers apply RoPE with `inp_pos`. The gated-delta-net layers don't use positions, so the garbage stays invisible until layer 3 in Qwen3.5-0.8B/2B.
2. **Why is a 1-token embd batch deterministic?** With one key, softmax is 1 and the output is V. The rotation of q and k cancels out.
3. **Why didn't threads, KV cache, flash attention or fused ops matter?** They all run after `inp_pos`. The garbage is in the host input data before any kernel runs.
4. **Is this an allocator bug like #29313?** No. Every intermediate before the RoPE was bitwise identical. The difference entered through the `inp_pos` input, copied from a host array that was too short.
5. **Why not just read `n_tokens` positions and broadcast `(p,p,p,0)` like the token path?** That would break callers that already pass 4 rows for images (the old mtmd `decode_embd_batch` pattern), and there is a test for that convention. The fix removes the out-of-bounds read without changing the API meaning. A maintainer could still choose the broadcast option.
6. **After the fix, does embd input with only `pos[i]` match the token path?** No. It becomes `(p,0,0,0)` instead of `(p,p,p,0)`: deterministic, but a different rotation for sections 1..2. For token-equivalent results, pass all 4 rows or use `llama_batch_ext_set_pos`.
7. **What if the caller allocates `pos` itself with n entries?** It still over-reads. The legacy struct carries no length, so the library can't detect it. That is why the header now documents the requirement.
8. **Why `calloc` and not `malloc`?** A larger `malloc` would stop the out-of-bounds read but leave the extra rows uninitialized, so results would still vary between runs. Zeroing makes them deterministic.
9. **How did you prove the garbage came from the heap?** The repro filled freed heap chunks with 0x40 bytes, and 1077952576 (0x40404040) showed up in `inp_pos`. Valgrind also reports the invalid read at the exact line.
10. **Why is the GET_ROWS on `inp_tokens` also "different" in the tensor dump?** It is the unselected branch of `ggml_build_forward_select`. It has no COMPUTE flag, so the CPU backend never runs it, and the callback sees an unwritten buffer. It does not affect the output.
