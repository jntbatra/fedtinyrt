#ifndef FEDTINYRT_SLEEP_REPLAY_H
#define FEDTINYRT_SLEEP_REPLAY_H
#include "sleep_core.h"
#define SLEEP_REPLAY_SECONDS 100u
/* SYNTHETIC control-flow fixture with scripted probabilities, NOT ML inference.
 * Firmware starts this explicitly labelled fixture until a real backend exists. */
bool sleep_replay_frame(uint32_t index, uint64_t now_ms, sleep_frame_t *frame);
#endif
