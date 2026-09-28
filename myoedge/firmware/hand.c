/* HACKberry-style hand around a myoedge-generated decoder.
 *
 * Board pieces are the hal_* hooks: an 8-channel EMG front end sampled at
 * 200 Hz (int8, zero-centred), three hobby servos (thumb, index, the coupled
 * middle-ring-little), and one button. Holding the button while making a fist
 * for three seconds recalibrates for how the band sits today.
 *
 * RAM: the decoder struct plus eight calibration counters.
 */
#include <stdint.h>
#include "myo.h"
#include "calibration_ref.h"   /* CAL_REF[8], written by `myoedge emit` */

void hal_wait_sample(void);                 /* blocks until the next 5 ms tick */
void hal_read_emg(int8_t s[MYO_CH]);
void hal_servo(uint8_t which, int16_t degrees);
int hal_button(void);

#define CAL_SAMPLES (3 * 200)

static myo_t dec;

static int8_t calibrate(void)
{
    myo_cal_t c;
    int8_t s[MYO_CH];
    myo_cal_reset(&c);
    for (int i = 0; i < CAL_SAMPLES; ++i) {
        hal_wait_sample();
        hal_read_emg(s);
        myo_cal_push(&c, s);
    }
    return myo_cal_finish(&c, CAL_REF);
}

void hand_run(void)
{
    int8_t s[MYO_CH];
    myo_init(&dec, 0);
    for (;;) {
        if (hal_button())
            myo_init(&dec, calibrate());
        hal_wait_sample();
        hal_read_emg(s);
        if (myo_push(&dec, s) >= 0)
            for (uint8_t i = 0; i < 3; ++i) hal_servo(i, dec.servo[i]);
    }
}
