// Host playground for the steering knob and the attention tap, so both can be
// tuned before any hardware exists.
//
// Generates greedily from one prompt token at several gamma values and prints
// the token ids, so you can see where the sequences diverge. Then prints the
// watched head's attention over positions -- the same numbers the LED ring will
// show, as text.
//
//   cc -O2 -DLLM_STEER -DLLM_ATTN_VIZ -o /tmp/steer runtime/host_verify/steer_demo.c -lm
//   /tmp/steer artifacts/tinystories/model.bin
//
// Optional args: <start_token> <layer> <n_tokens> <tokA> <tokB>

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "../llm.h"

static uint8_t *read_file(const char *path, size_t *n) {
  FILE *f = fopen(path, "rb");
  if (!f) { perror(path); exit(1); }
  fseek(f, 0, SEEK_END); *n = ftell(f); fseek(f, 0, SEEK_SET);
  uint8_t *b = malloc(*n);
  if (fread(b, 1, *n, f) != *n) { fprintf(stderr, "short read\n"); exit(1); }
  fclose(f); return b;
}

static Scratch alloc_scratch(const Model *m) {
  int D = m->c.dim, L = m->c.n_layers, P = m->c.ple_dim, F = m->c.ffn;
  int V = m->out_vocab, S = m->c.seq_len;
  Scratch s;
  s.x = malloc(D * 4); s.h = malloc((F > D ? F : D) * 4);
  s.qkv = malloc(3 * D * 4); s.att = malloc(D * 4);
  s.g1 = malloc(F * 4); s.g2 = malloc((P > F ? P : F) * 4);
  s.ple = malloc((size_t)L * P * 4); s.tmpP = malloc((size_t)L * P * 4);
  s.trow = malloc((size_t)L * P * 4);
  s.logits = malloc((size_t)V * 4); s.scores = malloc(S * 4);
  s.kcache = malloc((size_t)L * S * D * 4);
  s.vcache = malloc((size_t)L * S * D * 4);
  return s;
}

// Greedy decode from one token. Returns the ids it produced.
static void run(Model *m, Scratch *s, int start, int n, int *out) {
  int tok = start;
  for (int pos = 0; pos < n; pos++) {
    llm_forward(m, tok, pos, s);
    int best = 0;
    for (int i = 1; i < m->out_vocab; i++)
      if (s->logits[i] > s->logits[best]) best = i;
    out[pos] = best;
    tok = best;
  }
}

int main(int argc, char **argv) {
  if (argc < 2) { fprintf(stderr, "usage: %s <model.bin> [start layer n tokA tokB]\n", argv[0]); return 2; }
  int start = argc > 2 ? atoi(argv[2]) : 1;
  int layer = argc > 3 ? atoi(argv[3]) : 2;
  int n     = argc > 4 ? atoi(argv[4]) : 12;
  int tokA  = argc > 5 ? atoi(argv[5]) : 100;
  int tokB  = argc > 6 ? atoi(argv[6]) : 200;

  size_t nbytes;
  uint8_t *buf = read_file(argv[1], &nbytes);
  Model m;
  if (llm_load(buf, &m)) { fprintf(stderr, "bad magic\n"); return 1; }
  printf("model: D=%d L=%d H=%d S=%d Vout=%d\n",
         m.c.dim, m.c.n_layers, m.c.n_heads, m.c.seq_len, m.out_vocab);

  Scratch s = alloc_scratch(&m);

  // Cheap direction: difference of two token embeddings. Crude on purpose --
  // it needs no host tooling and proves the injection path end to end.
  steer_from_token_pair(&m, tokA, tokB);
  g_steer.layer = layer;
  g_steer.relative = 1;
  g_attn.layer = layer;
  g_attn.head = 0;
  printf("steering at layer %d, vector = emb[%d] - emb[%d], dim %d\n\n",
         layer, tokA, tokB, g_steer.dim);

  const float gammas[] = {0.f, 0.5f, 1.f, 2.f, 4.f};
  int *base = malloc(n * sizeof(int)), *out = malloc(n * sizeof(int));

  for (unsigned gi = 0; gi < sizeof(gammas) / sizeof(*gammas); gi++) {
    g_steer.gamma = gammas[gi];
    run(&m, &s, start, n, out);
    if (gi == 0) for (int i = 0; i < n; i++) base[i] = out[i];

    int diverge = -1;
    for (int i = 0; i < n; i++) if (out[i] != base[i]) { diverge = i; break; }

    printf("gamma %4.1f  ", gammas[gi]);
    for (int i = 0; i < n; i++) printf("%5d", out[i]);
    if (gi == 0) printf("   (baseline)\n");
    else if (diverge < 0) printf("   identical\n");
    else printf("   diverges at token %d\n", diverge);
  }

  // The attention picture at the last decoded position, for the watched head.
  printf("\nattention, layer %d head %d, %d positions:\n", g_attn.layer, g_attn.head, g_attn.len);
  for (int t = 0; t < g_attn.len; t++) {
    int bar = (int)(sqrtf(g_attn.w[t]) * 40.f);
    printf("  pos %3d  %.4f  ", t, g_attn.w[t]);
    for (int i = 0; i < bar; i++) putchar('#');
    putchar('\n');
  }
  printf("\n(what this looks like depends on the layer: early layers put a\n"
         " visible lump on pos 0 -- the attention sink -- while later ones\n"
         " collapse onto the last two or three positions. Both show up on the\n"
         " ring; try -layer 0 and -layer 2 back to back.)\n");
  return 0;
}
