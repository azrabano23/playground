from pathlib import Path

import numpy as np
import pytest

from loopgraph.cgate import cc, compile_and_run
from myoedge.deploy import emit
from tests.test_deploy import model  # noqa: F401  (fixture)

FW = Path(__file__).resolve().parents[1] / "firmware"


@pytest.mark.skipif(cc() is None, reason="no C compiler")
def test_hand_loop_links_against_a_generated_decoder(model):  # noqa: F811
    m, _ = model
    srcs = {**emit(m), "hand.c": (FW / "hand.c").read_text(),
            "calibration_ref.h": "static const int32_t CAL_REF[8] = {1,1,1,1,1,1,1,1};\n"}
    stub = """#include <stdint.h>
void hand_run(void);
void hal_wait_sample(void) {}
void hal_read_emg(int8_t s[8]) { for (int i = 0; i < 8; ++i) s[i] = 0; }
void hal_servo(uint8_t w, int16_t d) { (void)w; (void)d; }
int hal_button(void) { return 0; }
int main(void) { return 0; }
"""
    compile_and_run(srcs, stub)
