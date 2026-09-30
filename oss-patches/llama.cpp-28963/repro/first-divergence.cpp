// Decode the same multi-token embd batch twice (pos from llama_batch_init, only pos[i] set)
// and report the first graph tensor whose contents differ between the two runs,
// plus the contents of the "inp_pos" tensor in each run.
//
// usage: first-divergence <model.gguf> [n_tokens]
#include "llama.h"
#include "ggml.h"
#include "ggml-backend.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>

struct rec { std::string name; std::string op; std::vector<uint8_t> data; };

static std::vector<rec> g_recs;

static bool cb_eval(struct ggml_tensor * t, bool ask, void *) {
    if (ask) return true;
    rec r; r.name = ggml_get_name(t);
    r.op = ggml_op_desc(t);
    for (int i = 0; i < GGML_MAX_SRC && t->src[i]; ++i) { r.op += i ? ", " : "("; r.op += ggml_get_name(t->src[i]); }
    if (t->src[0]) r.op += ")";
    r.data.resize(ggml_nbytes(t));
    ggml_backend_tensor_get(t, r.data.data(), 0, r.data.size());
    g_recs.push_back(std::move(r));
    // record the graph inputs too, via the first op that reads them
    for (int i = 0; i < GGML_MAX_SRC && t->src[i]; ++i) {
        if (std::string(ggml_get_name(t->src[i])) == "inp_pos") {
            rec p; p.name = "inp_pos";
            p.data.resize(ggml_nbytes(t->src[i]));
            ggml_backend_tensor_get(t->src[i], p.data.data(), 0, p.data.size());
            g_recs.push_back(std::move(p));
        }
    }
    return true;
}

int main(int argc, char ** argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s model.gguf [n_tokens]\n", argv[0]); return 1; }
    const int n_tok = argc > 2 ? atoi(argv[2]) : 5;

    llama_log_set([](ggml_log_level, const char *, void *) {}, nullptr);
    llama_backend_init();
    llama_model_params mp = llama_model_default_params();
    mp.n_gpu_layers = 0;
    llama_model * model = llama_model_load_from_file(argv[1], mp);
    llama_context_params cp = llama_context_default_params();
    cp.n_ctx = 512; cp.n_batch = 512; cp.n_ubatch = 512; cp.n_threads = 1; cp.n_threads_batch = 1;
    cp.cb_eval = cb_eval; cp.cb_eval_user_data = nullptr;
    llama_context * ctx = llama_init_from_model(model, cp);
    const int n_embd = llama_model_n_embd_inp(model);

    std::vector<float> embd((size_t) n_tok*n_embd);
    uint32_t s = 12345;
    for (auto & v : embd) { s = s*1664525u + 1013904223u; v = ((s >> 8) / 16777216.0f - 0.5f) * 0.05f; }

    std::vector<std::vector<rec>> runs;
    for (int r = 0; r < 2; ++r) {
        llama_memory_clear(llama_get_memory(ctx), true);
        // unrelated heap traffic between runs, as a real application would have
        std::vector<void *> junk; for (int k = 0; k < 64; ++k) { junk.push_back(malloc(16 + k)); memset(junk.back(), 0x40 + r, 16 + k); }
        for (void * p : junk) free(p);

        llama_batch b = llama_batch_init(n_tok, n_embd, 1);
        b.n_tokens = n_tok;
        memcpy(b.embd, embd.data(), embd.size()*sizeof(float));
        for (int i = 0; i < n_tok; ++i) { b.pos[i] = i; b.n_seq_id[i] = 1; b.seq_id[i][0] = 0; b.logits[i] = 1; }
        g_recs.clear();
        if (llama_decode(ctx, b) != 0) { fprintf(stderr, "decode failed\n"); return 1; }
        runs.push_back(g_recs);
        llama_batch_free(b);
    }

    for (int r = 0; r < 2; ++r) {
        for (auto & rc : runs[r]) {
            if (rc.name != "inp_pos") continue;
            const int32_t * p = (const int32_t *) rc.data.data();
            const size_t n = rc.data.size()/4;
            printf("run %d inp_pos (%zu = %d sections x %d tokens):", r, n, (int)(n/n_tok), n_tok);
            for (size_t i = 0; i < n; ++i) printf("%s%d", i % n_tok == 0 ? " | " : " ", p[i]);
            printf("\n");
            break;
        }
    }

    const size_t n = std::min(runs[0].size(), runs[1].size());
    for (size_t i = 0; i < n; ++i) {
        if (runs[0][i].name != runs[1][i].name) { printf("graph mismatch at node %zu\n", i); return 1; }
        // the token-id branch of ggml_build_forward_select() (GET_ROWS on inp_tokens) is not used for an
        // embd batch and its input is never set, so it is ignored here
        if (runs[0][i].op.find("inp_tokens") != std::string::npos) {
            if (runs[0][i].data != runs[1][i].data) printf("(ignored: #%zu %s = %s differs, unselected token branch)\n", i, runs[0][i].name.c_str(), runs[0][i].op.c_str());
            continue;
        }
        if (runs[0][i].data != runs[1][i].data) {
            printf("first differing tensor: #%zu '%s'\n", i, runs[0][i].name.c_str());
            // show the tensor before it for context
            if (i > 0) printf("previous tensor (identical): '%s'\n", runs[0][i-1].name.c_str());
            // name the ops that consume the first differing tensor's data in this graph order
            printf("evaluation order up to the first difference:\n");
            for (size_t k = (i > 3 ? i - 3 : 0); k <= i; ++k) printf("  #%zu %s = %s\n", k, runs[0][k].name.c_str(), runs[0][k].op.c_str());
            size_t shown = 0;
            printf("first differing tensors with a layer-tagged name:\n");
            for (size_t k = i; k < n && shown < 6; ++k) {
                if (runs[0][k].data != runs[1][k].data && runs[0][k].name.find('-') != std::string::npos) {
                    printf("  #%zu %s = %s\n", k, runs[0][k].name.c_str(), runs[0][k].op.c_str()); shown++;
                }
            }
            return 2;
        }
    }
    printf("all %zu evaluated tensors bitwise identical across the two runs\n", n);
    return 0;
}
