/* apnea_dash.c - on-LCD live apnea dashboard for the RA8P1 (cam2lcd base).
 *
 * Reuses the GLCDC display stack already configured by the mipi_csi example
 * (RGB565, 1024x600, single visible layer = fb_background; layer 2 disabled).
 * No camera is used. The INT8 apnea arithmetic is copied verbatim from
 * apnea_deploy/src/apnea.c, so board decisions stay bit-exact against the host
 * reference (see FINAL_RESULTS.md); nothing about the shipped model changes.
 *
 * Feature windows are streamed over the serial `feat <10 floats>` command -- the
 * same command apnea_deploy exposes -- so the existing host tool
 * (tools/live_demo.py) drives the board's own screen. Extra commands:
 *   dashreset          zero the running counters and repaint
 *   dashname <text>    show a subject/label string on screen
 *
 * Honesty (carried from FINAL_RESULTS.md, shown on screen too):
 *   * "AHI" here is the WINDOW-COUNT PROXY = predicted positive windows/hour.
 *     It is a proxy, not a scored clinical index; AHI is unresolved.
 *   * Pure CPU (Cortex-M85). No NPU. No energy claim.
 */

#include <math.h>
#include <string.h>

#include "common_utils.h"
#include "common_data.h"      /* fb_background, DISPLAY_*_INPUT0, g_display_ctrl */
#include "glcdc_display.h"
#include "apnea_model.h"
#include "feature_normalization_mean.h"
#include "feature_normalization_inverse_std.h"
#include "font8x8_basic.h"    /* public domain 8x8 font (Daniel Hepper) */

/* the camera EP normally sets these; we set them ourselves before glcdc_init */
extern uint16_t g_image_width;
extern uint16_t g_image_height;

/* ------------------------------------------------------------ framebuffer */

#define FB_W      (DISPLAY_HSIZE_INPUT0)                       /* 1024 */
#define FB_H      (DISPLAY_VSIZE_INPUT0)                       /* 600  */
#define FB_PITCH  (DISPLAY_BUFFER_STRIDE_BYTES_INPUT0 / 2)     /* px per row */

static uint16_t * const FB = (uint16_t *) (void *) &fb_background[0][0];

static inline uint16_t rgb565(uint8_t r, uint8_t g, uint8_t b)
{
    return (uint16_t) (((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
}

#define C_BG      rgb565( 12, 16, 22)
#define C_PANEL   rgb565( 24, 30, 40)
#define C_TEXT    rgb565(224,230,236)
#define C_DIM     rgb565(120,132,148)
#define C_ACCENT  rgb565( 46,196,182)
#define C_APNEA   rgb565(228, 64, 64)
#define C_NORMAL  rgb565( 58,190,110)

static void fill_rect(int x, int y, int w, int h, uint16_t c)
{
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > FB_W) { w = FB_W - x; }
    if (y + h > FB_H) { h = FB_H - y; }
    for (int j = 0; j < h; j++)
    {
        uint16_t * row = FB + (long) (y + j) * FB_PITCH + x;
        for (int i = 0; i < w; i++)
        {
            row[i] = c;
        }
    }
}

/* One 8x8 glyph, integer-scaled by s. font8x8 bit 0 = leftmost column. */
static void draw_glyph(int x, int y, char ch, int s, uint16_t fg)
{
    if ((unsigned char) ch >= 128)
    {
        ch = '?';
    }
    const char * g = font8x8_basic[(unsigned char) ch];
    for (int ry = 0; ry < 8; ry++)
    {
        unsigned char bits = (unsigned char) g[ry];
        for (int rx = 0; rx < 8; rx++)
        {
            if (bits & (1u << rx))
            {
                fill_rect(x + rx * s, y + ry * s, s, s, fg);
            }
        }
    }
}

static int draw_text(int x, int y, const char * str, int s, uint16_t fg)
{
    int cx = x;
    for (; *str; str++)
    {
        if (*str != ' ')
        {
            draw_glyph(cx, y, *str, s, fg);
        }
        cx += 8 * s;
    }
    return cx;
}

/* right-pads an int into a small buffer, returns pointer to it */
static void utoa_pad(uint32_t v, char * buf)
{
    char tmp[12];
    int n = 0;
    if (v == 0)
    {
        tmp[n++] = '0';
    }
    while (v)
    {
        tmp[n++] = (char) ('0' + (v % 10u));
        v /= 10u;
    }
    int k = 0;
    while (n)
    {
        buf[k++] = tmp[--n];
    }
    buf[k] = '\0';
}

/* value*10 (one decimal fixed point) -> "12.3" */
static void fixed1(uint32_t x10, char * buf)
{
    char whole[12];
    utoa_pad(x10 / 10u, whole);
    int k = 0;
    for (int i = 0; whole[i]; i++)
    {
        buf[k++] = whole[i];
    }
    buf[k++] = '.';
    buf[k++] = (char) ('0' + (x10 % 10u));
    buf[k] = '\0';
}

/* ------------------------------------------------------------ INT8 model
 * (verbatim from apnea_deploy/src/apnea.c -- keep bit-exact) */

static inline int8_t q_clamp(int32_t v)
{
    if (v > 127) { return (int8_t) 127; }
    if (v < -128) { return (int8_t) -128; }
    return (int8_t) v;
}

static inline int32_t rnd_double(double x)
{
    double a = (x < 0.0) ? -x : x;
    int32_t r = (int32_t) (a + 0.5);
    return (x < 0.0) ? -r : r;
}

static int8_t apnea_infer_q(const int8_t * x_in, float * prob)
{
    int8_t x1[APNEA_H1];
    int8_t x2[APNEA_H2];

    for (int j = 0; j < APNEA_H1; j++)
    {
        int32_t acc = apnea_b1[j];
        for (int i = 0; i < APNEA_IN_DIM; i++)
        {
            acc += (int32_t) apnea_w1[j][i] * ((int32_t) x_in[i] - APNEA_IN_ZP);
        }
        double mult = ((double) APNEA_IN_SCALE * (double) apnea_w1_scale[j]) / (double) APNEA_A1_SCALE;
        x1[j] = q_clamp(rnd_double((double) acc * mult) + APNEA_A1_ZP);
    }

    for (int j = 0; j < APNEA_H2; j++)
    {
        int32_t acc = apnea_b2[j];
        for (int i = 0; i < APNEA_H1; i++)
        {
            acc += (int32_t) apnea_w2[j][i] * ((int32_t) x1[i] - APNEA_A1_ZP);
        }
        double mult = ((double) APNEA_A1_SCALE * (double) apnea_w2_scale[j]) / (double) APNEA_A2_SCALE;
        x2[j] = q_clamp(rnd_double((double) acc * mult) + APNEA_A2_ZP);
    }

    int32_t acc = APNEA_B3;
    for (int i = 0; i < APNEA_H2; i++)
    {
        acc += (int32_t) apnea_w3[i] * ((int32_t) x2[i] - APNEA_A2_ZP);
    }
    double mult = ((double) APNEA_A2_SCALE * (double) APNEA_W3_SCALE) / (double) APNEA_HEAD_SCALE;
    int8_t q9 = q_clamp(rnd_double((double) acc * mult) + APNEA_HEAD_ZP);

    double logit = ((double) q9 - (double) APNEA_HEAD_ZP) * (double) APNEA_HEAD_SCALE;
    double p     = 1.0 / (1.0 + exp(-logit));
    int8_t q10   = q_clamp(rnd_double(p / (double) APNEA_OUT_SCALE) + APNEA_OUT_ZP);

    *prob = (float) p;
    return q10;
}

static void apnea_normalize_q(const float * raw, int8_t * x_in)
{
    for (int i = 0; i < APNEA_IN_DIM; i++)
    {
        double n = ((double) raw[i] - (double) g_feature_normalization_mean[i]) *
                   (double) g_feature_normalization_inverse_std[i];
        x_in[i] = q_clamp(rnd_double(n / (double) APNEA_IN_SCALE) + APNEA_IN_ZP);
    }
}

/* feat float parser (verbatim from apnea.c) */
static int parse_floats(const char * s, float * out, int n)
{
    const char * p = s;
    for (int i = 0; i < n; i++)
    {
        while (*p == ' ' || *p == '\t' || *p == ',') { p++; }
        if (*p == '\0') { return 0; }
        int neg = 0;
        double v = 0.0;
        if (*p == '+' || *p == '-') { neg = (*p == '-'); p++; }
        int digits = 0;
        while (*p >= '0' && *p <= '9') { v = v * 10.0 + (double) (*p - '0'); p++; digits++; }
        if (*p == '.')
        {
            p++;
            double f = 0.1;
            while (*p >= '0' && *p <= '9') { v += (double) (*p - '0') * f; f *= 0.1; p++; digits++; }
        }
        if (digits == 0) { return 0; }
        if (*p == 'e' || *p == 'E')
        {
            p++;
            int eneg = 0;
            if (*p == '+' || *p == '-') { eneg = (*p == '-'); p++; }
            int e = 0;
            while (*p >= '0' && *p <= '9') { e = e * 10 + (*p - '0'); p++; }
            double scale = 1.0;
            for (int k = 0; k < e; k++) { scale *= 10.0; }
            v = eneg ? (v / scale) : (v * scale);
        }
        out[i] = (float) (neg ? -v : v);
    }
    return 1;
}

/* ------------------------------------------------------------ dashboard */

#define STRIDE_S   (30u)     /* one window per 30 s of night */

static uint32_t g_win;       /* windows streamed this run   */
static uint32_t g_pos;       /* predicted-apnea windows     */
static int      g_last;      /* last decision: 1 apnea 0 normal -1 none */
static float    g_lastp;
static char     g_name[40] = "";

/* layout anchors */
#define VERD_X 40
#define VERD_Y 150
#define VERD_W 560
#define VERD_H 210
#define RIGHT_X 640

static void dash_static(void)
{
    fill_rect(0, 0, FB_W, FB_H, C_BG);
    /* title bar */
    fill_rect(0, 0, FB_W, 74, C_PANEL);
    draw_text(28, 22, "RA8P1  APNEA SCREENING  -  LIVE", 3, C_ACCENT);
    /* verdict panel frame */
    fill_rect(VERD_X, VERD_Y, VERD_W, VERD_H, C_PANEL);
    /* right column labels */
    draw_text(RIGHT_X, 150, "AHI  WINDOW PROXY", 2, C_DIM);
    draw_text(RIGHT_X, 300, "WINDOWS", 2, C_DIM);
    draw_text(RIGHT_X, 400, "APNEA WINDOWS", 2, C_DIM);
    /* honesty footer */
    draw_text(28, 520, "AHI = PREDICTED POSITIVE WINDOWS/HOUR - PROXY, NOT A", 2, C_DIM);
    draw_text(28, 545, "CLINICAL INDEX.  INT8 MODEL ON CPU.  NO NPU, NO ENERGY CLAIM.", 2, C_DIM);
}

static void dash_dynamic(void)
{
    /* subject name (top-right of title) */
    fill_rect(RIGHT_X, 22, FB_W - RIGHT_X - 20, 28, C_PANEL);
    if (g_name[0])
    {
        draw_text(RIGHT_X, 22, g_name, 3, C_TEXT);
    }

    /* verdict */
    fill_rect(VERD_X + 6, VERD_Y + 6, VERD_W - 12, VERD_H - 12,
              (g_last == 1) ? C_APNEA : (g_last == 0) ? C_NORMAL : C_PANEL);
    const char * word = (g_last == 1) ? "APNEA" : (g_last == 0) ? "NORMAL" : "----";
    int s = 11;
    int tw = (int) strlen(word) * 8 * s;
    draw_text(VERD_X + (VERD_W - tw) / 2, VERD_Y + (VERD_H - 8 * s) / 2, word, s,
              rgb565(255, 255, 255));

    /* prob under the panel */
    fill_rect(VERD_X, VERD_Y + VERD_H + 14, VERD_W, 40, C_BG);
    char pb[16];
    if (g_last >= 0)
    {
        uint32_t p1000 = (uint32_t) (g_lastp * 1000.0f + 0.5f);
        char frac[8];
        char whole[4];
        utoa_pad(p1000 / 1000u, whole);
        int k = 0;
        pb[k++] = whole[0];
        pb[k++] = '.';
        uint32_t f = p1000 % 1000u;
        pb[k++] = (char) ('0' + (f / 100u));
        pb[k++] = (char) ('0' + ((f / 10u) % 10u));
        pb[k++] = (char) ('0' + (f % 10u));
        pb[k] = '\0';
        (void) frac;
        draw_text(VERD_X, VERD_Y + VERD_H + 14, "PROB ", 3, C_DIM);
        draw_text(VERD_X + 8 * 3 * 5, VERD_Y + VERD_H + 14, pb, 3, C_TEXT);
    }

    /* AHI proxy (one decimal) */
    fill_rect(RIGHT_X, 185, FB_W - RIGHT_X - 20, 90, C_BG);
    uint32_t ahi10 = g_win ? (uint32_t) (((uint64_t) g_pos * 3600u * 10u) /
                                         ((uint64_t) g_win * STRIDE_S)) : 0u;
    char ab[16];
    fixed1(ahi10, ab);
    int ex = draw_text(RIGHT_X, 185, ab, 8, C_ACCENT);
    draw_text(ex + 12, 215, "/H", 3, C_DIM);

    /* window + apnea counts */
    fill_rect(RIGHT_X, 335, FB_W - RIGHT_X - 20, 50, C_BG);
    char nb[16];
    utoa_pad(g_win, nb);
    draw_text(RIGHT_X, 335, nb, 6, C_TEXT);

    fill_rect(RIGHT_X, 435, FB_W - RIGHT_X - 20, 50, C_BG);
    utoa_pad(g_pos, nb);
    draw_text(RIGHT_X, 435, nb, 6, C_TEXT);
}

static void dash_reset(void)
{
    g_win = 0;
    g_pos = 0;
    g_last = -1;
    g_lastp = 0.0f;
    dash_dynamic();
}

static void cmd_feat(const char * args)
{
    float raw[APNEA_IN_DIM];
    if (!parse_floats(args, raw, APNEA_IN_DIM))
    {
        TERM_PRINTF("  usage: feat <10 floats>\r\n");
        return;
    }
    int8_t x_in[APNEA_IN_DIM];
    apnea_normalize_q(raw, x_in);
    float prob;
    int8_t q = apnea_infer_q(x_in, &prob);
    int apnea = (q >= APNEA_THRESHOLD_Q);

    g_win++;
    if (apnea) { g_pos++; }
    g_last = apnea ? 1 : 0;
    g_lastp = prob;
    dash_dynamic();

    /* serial reply -- same shape apnea.c prints, so the host tool still parses */
    TERM_PRINTF("  prob_q : %d\r\n", (int) q);
    TERM_PRINTF("  prob   : %d.%04d\r\n",
                (int) prob, (int) ((prob - (float) (int) prob) * 10000.0f));
    TERM_PRINTF("  decision: %s (q %s %d)\r\n",
                apnea ? "APNEA" : "normal",
                apnea ? ">=" : "<", APNEA_THRESHOLD_Q);
}

/* --------------------------------------------------------------- entry */

void apnea_dash_entry(void);
void apnea_dash_entry(void)
{
    static char line[512];

    /* the camera would set these; we drive the panel at its native size */
    g_image_width  = FB_W;
    g_image_height = FB_H;

    glcdc_init();
    TERM_INIT();

    dash_static();
    dash_reset();

    TERM_PRINTF("\r\n== RA8P1 apnea LCD dashboard ==\r\n");
    TERM_PRINTF("cmds: feat <10 floats> | dashreset | dashname <text>\r\n");

    for (;;)
    {
        uint32_t n = 0;
        while (n == 0u)
        {
            if (TERM_HAS_DATA())
            {
                n = TERM_READ(line, sizeof(line) - 1u);
            }
        }
        line[n] = '\0';
        while (n > 0u && (line[n - 1u] == ' ' || line[n - 1u] == '\t' ||
                          line[n - 1u] == '\r' || line[n - 1u] == '\n'))
        {
            line[--n] = '\0';
        }
        if (n == 0u) { continue; }

        if (strncmp(line, "feat ", 5) == 0)
        {
            cmd_feat(line + 5);
        }
        else if (strcmp(line, "dashreset") == 0)
        {
            dash_reset();
            TERM_PRINTF("  reset\r\n");
        }
        else if (strncmp(line, "dashname ", 9) == 0)
        {
            strncpy(g_name, line + 9, sizeof(g_name) - 1u);
            g_name[sizeof(g_name) - 1u] = '\0';
            dash_dynamic();
            TERM_PRINTF("  name %s\r\n", g_name);
        }
        else
        {
            TERM_PRINTF("  cmds: feat <10 floats> | dashreset | dashname <text>\r\n");
        }
    }
}
