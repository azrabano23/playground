// Repro for ggml-org/llama.cpp#28963: decode the same batch N times with a
// cleared memory and hash the logits of every position.
//
// usage: embd-determinism <model.gguf> <embd|tokens> <n_tokens> <n_runs> [n_threads] [pos_mode]
//   pos_mode: "n"    - batch from llama_batch_init(), pos[i] = i for i < n_tokens (default, like most callers)
//             "full" - pos array sized n_tokens*4 in the M-RoPE section-major layout (what mtmd does)
//             "null" - batch.pos = nullptr (positions auto-generated)
#include "llama.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cmath>
#include <map>
#include <string>
#include <vector>

static uint64_t fnv1a(const void * data, size_t n, uint64_t h = 1469598103934665603ULL) {
    const uint8_t * p = (const uint8_t *) data;
    for (size_t i = 0; i < n; ++i) { h ^= p[i]; h *= 1099511628211ULL; }
    return h;
}

int main(int argc, char ** argv) {
    if (argc < 5) {
        fprintf(stderr, "usage: %s model.gguf embd|tokens n_tokens n_runs [n_threads]\n", argv[0]);
        return 1;
    }
    const char * path    = argv[1];
    const bool   use_emb = std::string(argv[2]) == "embd";
    const int    n_tok   = atoi(argv[3]);
    const int    n_runs  = atoi(argv[4]);
    const int    n_thr   = argc > 5 ? atoi(argv[5]) : 1;
    const std::string pos_mode = argc > 6 ? argv[6] : "n";

    llama_log_set([](ggml_log_level, const char *, void *) {}, nullptr);
    llama_backend_init();

    llama_model_params mp = llama_model_default_params();
    mp.n_gpu_layers = 0;
    llama_model * model = llama_model_load_from_file(path, mp);
    if (!model) { fprintf(stderr, "failed to load model\n"); return 1; }

    llama_context_params cp = llama_context_default_params();
    cp.n_ctx = 512; cp.n_batch = 512; cp.n_ubatch = 512;
    cp.n_threads = n_thr; cp.n_threads_batch = n_thr;
    cp.no_perf = true;
    llama_context * ctx = llama_init_from_model(model, cp);
    if (!ctx) { fprintf(stderr, "failed to create context\n"); return 1; }

    const int n_embd  = llama_model_n_embd_inp(model);
    const int n_vocab = llama_vocab_n_tokens(llama_model_get_vocab(model));

    // deterministic input
    std::vector<float>       embd((size_t) n_tok*n_embd);
    std::vector<llama_token> toks(n_tok);
    uint32_t s = 12345;
    for (auto & v : embd) { s = s*1664525u + 1013904223u; v = ((s >> 8) / 16777216.0f - 0.5f) * 0.05f; }
    for (int i = 0; i < n_tok; ++i) toks[i] = (1000 + 17*i) % n_vocab;

    std::map<uint64_t, int> seen;
    for (int r = 0; r < n_runs; ++r) {
        llama_memory_clear(llama_get_memory(ctx), true);

        llama_batch b = llama_batch_init(n_tok, use_emb ? n_embd : 0, 1);
        b.n_tokens = n_tok;
        std::vector<llama_pos> pos_full;
        if (pos_mode == "full") {
            pos_full.resize((size_t) n_tok*4);
            for (int j = 0; j < 4; ++j) for (int i = 0; i < n_tok; ++i) pos_full[(size_t) j*n_tok + i] = j < 3 ? i : 0;
        }
        for (int i = 0; i < n_tok; ++i) {
            if (use_emb) memcpy(b.embd + (size_t) i*n_embd, embd.data() + (size_t) i*n_embd, n_embd*sizeof(float));
            else         b.token[i] = toks[i];
            b.pos[i] = i; b.n_seq_id[i] = 1; b.seq_id[i][0] = 0; b.logits[i] = 1;
        }
        llama_pos * pos_orig = b.pos;
        if (pos_mode == "full") b.pos = pos_full.data();
        if (pos_mode == "null") b.pos = nullptr;
        const int ret = llama_decode(ctx, b);
        b.pos = pos_orig;
        if (ret != 0) { fprintf(stderr, "decode failed\n"); return 1; }

        uint64_t h = 1469598103934665603ULL;
        for (int i = 0; i < n_tok; ++i) h = fnv1a(llama_get_logits_ith(ctx, i), (size_t) n_vocab*sizeof(float), h);
        const float * last = llama_get_logits_ith(ctx, n_tok - 1);
        printf("run %2d: hash %016llx  logit[0]=%.9g\n", r, (unsigned long long) h, last[0]);
        seen[h]++;
        llama_batch_free(b);
    }
    printf("mode=%s pos=%s n_tokens=%d runs=%d distinct_hashes=%zu\n", use_emb ? "embd" : "tokens", pos_mode.c_str(), n_tok, n_runs, seen.size());

    llama_free(ctx);
    llama_model_free(model);
    llama_backend_free();
    return seen.size() == 1 ? 0 : 2;
}
