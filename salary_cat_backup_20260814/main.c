/*
 * salary_cat: "Salary Cat" screensaver on the onboard 0.96" SSD1306 OLED
 * (128x64) over hardware I2C0 (PA0=SDA, PA1=SCL).
 * The 22-frame dance (96x48 sprites, 0.75x box-filter majority-vote
 * downscale from the reference 128x64 frames) plays while the sprite
 * moves in a three-phase loop (screensaver style):
 *   Phase A: left -> right  : start (-96, 8),  dx=1 dy=0, until x > 127
 *   Phase B: top -> bottom  : start (16, -48), dx=0 dy=1, until y > 63
 *   Phase C: bottom-right -> top-left: start (128, 64), dx=-1 dy=-1,
 *            until x < -96, then back to Phase A.
 * Dance and movement are decoupled on a common 10 ms timebase (the GCD
 * of 20 and 50):
 *   - Movement: 1 px every 20 ms (MOVE_INTERVAL_MS)
 *   - Dance:    1 frame every 50 ms (FRAME_INTERVAL_MS)
 * The whole framebuffer is cleared before every draw (OLED_Clear) so no
 * pixels from the previous position linger (no ghosting / trails).
 * Sprite start/end positions are off-screen by design; the draw is skipped
 * while fully off-screen.
 * Runs in default 32 MHz RUN mode (no STOP2 / no __WFI).
 */
#include "ti_msp_dl_config.h"
#include "OLED.h"
#include "cat_frames.h"

#define MOVE_INTERVAL_MS 20          /* 1 px movement every 20 ms */
#define FRAME_INTERVAL_MS 50         /* 1 dance frame every 50 ms */
#define TICK_MS 10                   /* common timebase = GCD(20, 50) */

#define SCR_W 128
#define SCR_H 64

/* Sprite fully off-screen (draw nothing; start/end of phases are off-screen) */
#define SPRITE_OFFSCREEN(x, y) \
    ((x) + CAT_SPRITE_W <= 0 || (x) >= SCR_W || \
     (y) + CAT_SPRITE_H <= 0 || (y) >= SCR_H)

int main(void)
{
    int16_t x = -96, y = 8;          /* Phase A start position */
    int8_t dx = 1, dy = 0;
    uint8_t frame = 0;
    uint8_t phase = 0;               /* 0=A, 1=B, 2=C */
    uint32_t tick = 0;               /* 10 ms ticks since power-on */

    SYSCFG_DL_init();
    OLED_Init();
    OLED_Clear();

    /* Power-on: frame 0 at Phase A start (offscreen by design) */
    if (!SPRITE_OFFSCREEN(x, y)) {
        OLED_ShowImage(x, y, CAT_SPRITE_W, CAT_SPRITE_H, cat_frames[0]);
    }
    OLED_Update();

    while (1) {
        delay_cycles(CPUCLK_FREQ / 1000 * TICK_MS); /* 10 ms base tick */
        tick++;

        uint8_t moved = 0, framed = 0;

        /* Movement: exactly 1 px every 20 ms (tick % 2 == 0) */
        if (tick % (MOVE_INTERVAL_MS / TICK_MS) == 0) {
            x += dx;
            y += dy;
            moved = 1;

            /* Phase transitions (each phase ends when fully off-screen) */
            if (phase == 0 && x > 127) {         /* A: moved fully past right edge */
                phase = 1;
                x = 16; y = -48; dx = 0; dy = 1; /* B start */
            } else if (phase == 1 && y > 63) {   /* B: moved fully past bottom edge */
                phase = 2;
                x = 128; y = 64; dx = -1; dy = -1; /* C start */
            } else if (phase == 2 && x < -96) {  /* C: moved fully past top-left */
                phase = 0;
                x = -96; y = 8; dx = 1; dy = 0;  /* A start */
            }
        }

        /* Dance: exactly 1 frame every 50 ms (tick % 5 == 0) */
        if (tick % (FRAME_INTERVAL_MS / TICK_MS) == 0) {
            frame = (frame + 1) % CAT_FRAME_COUNT;
            framed = 1;
        }

        /* Redraw only when something changed. When move and frame fire on the
         * same tick (every LCM(20,50) = 100 ms) this runs exactly once. */
        if (moved || framed) {
            /* Clear whole framebuffer first, then draw the sprite at the new
             * position: no pixels left over from the previous frame (no trails). */
            OLED_Clear();
            if (!SPRITE_OFFSCREEN(x, y)) {
                OLED_ShowImage(x, y, CAT_SPRITE_W, CAT_SPRITE_H, cat_frames[frame]);
            }
            OLED_Update();
        }
    }
}
