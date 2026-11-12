// Host harness for oled_lang.h: runs programs separated by a line holding only "\x01", draws into a
// framebuffer with the same algorithms as research/oled/lang.py's Screen, and prints per program either
// "OK <fnv of each frame, comma-separated>" or "ERR <reason>". research/oled/test_c.py compares the two.
#include <stdio.h>
#include <stdlib.h>
#include "../oled_lang.h"

#define W 128
#define H 64
typedef struct { uint8_t px[W * H]; char out[1 << 16]; int outn; } fb;

static void put(fb *f, int x, int y) { if (x >= 0 && x < W && y >= 0 && y < H) f->px[y * W + x] = 1; }
static void frame(fb *f) {
  uint64_t h = 1469598103934665603ULL;
  for (int i = 0; i < W * H; i++) { h ^= f->px[i]; h *= 1099511628211ULL; }
  f->outn += snprintf(f->out + f->outn, sizeof f->out - f->outn, "%s%016llx", f->outn > 3 ? "," : "", (unsigned long long)h);
}
static void c_clear(void *c) { memset(((fb *)c)->px, 0, W * H); }
static void c_text(void *c, int x, int y, const char *s) {
  for (int i = 0; s[i]; i++) if (s[i] != ' ')
    for (int dx = 0; dx < 5; dx++) for (int dy = 0; dy < 7; dy++) if ((dx + dy) % 2 == 0) put(c, x + i * 6 + dx, y + dy);
}
static void c_pixel(void *c, int x, int y) { put(c, x, y); }
static void c_line(void *c, int x0, int y0, int x1, int y1) {
  int dx = abs(x1 - x0), dy = -abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1, err = dx + dy;
  for (int k = 0; k < W + H + 2; k++) {
    put(c, x0, y0);
    if (x0 == x1 && y0 == y1) break;
    int e2 = 2 * err;
    if (e2 >= dy) { err += dy; x0 += sx; }
    if (e2 <= dx) { err += dx; y0 += sy; }
  }
}
static void c_rect(void *c, int x, int y, int w, int h) {
  if (w <= 0 || h <= 0) return;
  c_line(c, x, y, x + w - 1, y); c_line(c, x, y + h - 1, x + w - 1, y + h - 1);
  c_line(c, x, y, x, y + h - 1); c_line(c, x + w - 1, y, x + w - 1, y + h - 1);
}
static void c_fill(void *c, int x, int y, int w, int h) {
  for (int yy = y < 0 ? 0 : y; yy < (y + h < H ? y + h : H); yy++)
    for (int xx = x < 0 ? 0 : x; xx < (x + w < W ? x + w : W); xx++) ((fb *)c)->px[yy * W + xx] = 1;
}
static void c_circle(void *c, int cx, int cy, int r) {
  int x = r, y = 0, err = 1 - r;
  while (x >= y) {
    int pts[8][2] = {{x, y}, {y, x}, {-y, x}, {-x, y}, {-x, -y}, {-y, -x}, {y, -x}, {x, -y}};
    for (int k = 0; k < 8; k++) put(c, cx + pts[k][0], cy + pts[k][1]);
    y++;
    if (err < 0) err += 2 * y + 1; else { x--; err += 2 * (y - x) + 1; }
  }
}
static void c_wait(void *c, int ms) { (void)ms; frame(c); }
static void c_done(void *c) { frame(c); }

static ol_machine M;
static fb F;
int main(void) {
  static char buf[1 << 24]; size_t n = fread(buf, 1, sizeof buf - 1, stdin); buf[n] = 0;
  ol_io io = {&F, c_clear, c_text, c_pixel, c_line, c_rect, c_fill, c_circle, c_wait, c_done};
  char *p = buf;
  while (*p) {
    char *end = strstr(p, "\n\x01\n");
    if (end) *end = 0;
    memset(&F, 0, sizeof F); strcpy(F.out, "OK ");  F.outn = 3;
    if (ol_parse(&M, p) != 0) printf("ERR %s\n", M.err);
    else if (ol_run(&M, &io) != 0) printf("ERR %s\n", M.err);
    else printf("%s\n", F.out);
    if (!end) break;
    p = end + 3;
  }
  return 0;
}
