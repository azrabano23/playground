# Repro for llama.cpp #28963

Base: ggml-org/llama.cpp master 1c47294 (2026-09-28), Linux x86-64, CPU only.

## Build

    git clone --depth 50 https://github.com/ggml-org/llama.cpp && cd llama.cpp
    cmake -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo -DLLAMA_CURL=OFF
    cmake --build build -j --target llama test-batch-alloc test-llama-archs
    L=$PWD
    g++ -O1 -g -std=c++17 embd-determinism.cpp -I$L/include -I$L/ggml/include -L$L/build/bin \
        -lllama -lggml -lggml-base -Wl,-rpath,$L/build/bin -o embd-determinism
    g++ -O1 -g -std=c++17 first-divergence.cpp -I$L/include -I$L/ggml/include -L$L/build/bin \
        -lllama -lggml -lggml-base -Wl,-rpath,$L/build/bin -o first-divergence

## Models

    # real model (833 MB)
    curl -L -o Qwen3.5-0.8B-Q8_0.gguf https://huggingface.co/ggml-org/Qwen3.5-0.8B-GGUF/resolve/main/Qwen3.5-0.8B-Q8_0.gguf
    # tiny random-weight qwen35 (5 MB), full attention every 2nd layer
    ./build/bin/test-llama-archs -a qwen35 -s 42 -o tinymodels   # -> tinymodels/qwen35-dense.gguf

## Run

    # args: model  embd|tokens  n_tokens  n_runs  n_threads  pos_mode(n|full|null)
    ./embd-determinism Qwen3.5-0.8B-Q8_0.gguf embd 5 6 4 n     # exit 2 + distinct_hashes>1 on the bug
    ./first-divergence Qwen3.5-0.8B-Q8_0.gguf 5                 # prints inp_pos + first differing tensor
    ./build/bin/test-batch-alloc                                 # new test: embd_batch_init_mrope_pos_in_bounds
    valgrind --error-exitcode=9 ./build/bin/test-batch-alloc

## Results (distinct logits hashes over N runs)

| case                                  | before (0.8B, 6 runs) | after (0.8B) | before (tiny, 8 runs) | after (tiny) |
|---------------------------------------|---------------|--------------|----------------|--------------|
| tokens, 5 tok                         | 1             | 1            | 1              | 1            |
| embd, 1 tok, pos[i] only              | 1             | -            | 1              | 1            |
| embd, 5 tok, pos[i] only, 4 threads   | **6**         | 1            | **8**          | 1            |
| embd, 5 tok, pos[i] only, 1 thread    | **6**         | -            | **8**          | 1            |
| embd, 5 tok, full 4*n pos             | 1             | 1            | 1              | 1            |
| embd, 5 tok, pos = NULL               | 1             | -            | 1              | 1            |

First differing tensor before the fix: `Qcur-3 = ROPE(Qcur_normed-3, inp_pos)` on 0.8B, `Qcur-1` on the tiny model.
After the fix, all 1423 (0.8B) / 131 (tiny) evaluated tensors are bitwise identical.

test-batch-alloc: before 6 of 340 assertions failed, valgrind 9 errors ("Invalid read of size 4 ... llama-batch.cpp:1286,
0 bytes after a block of size 12"). After: 0 failures, 0 valgrind errors.

Files: before-*.txt / after-*.txt hold the raw outputs.
