#include "sleep_replay.h"
#include <string.h>
bool sleep_replay_frame(uint32_t i, uint64_t now, sleep_frame_t *f)
{
    if (i >= SLEEP_REPLAY_SECONDS) return false;
    memset(f, 0, sizeof(*f));
    f->timestamp_ms = now;
    for (unsigned m = 0; m < SLEEP_MODALITIES; m++) {
        f->modality[m].present = f->modality[m].live = true;
        f->modality[m].quality = 1.f;
        f->modality[m].timestamp_ms = now;
    }
    bool event = i >= 40u && i < 60u;
    f->modality[SLEEP_SPO2].value = event ? 89.f : 97.f;
    f->modality[SLEEP_RESP].value = event ? .2f : 1.f;
    f->modality[SLEEP_MOTION].value = .05f;
    f->modality[SLEEP_AUDIO].value = .2f;
    f->event_probability = event ? .9f : .1f;
    f->inference_valid = true; /* Scripted fixture oracle, stated in telemetry. */
    if (i >= 80u && i < 85u) {
        f->modality[SLEEP_SPO2].present = false;
        f->modality[SLEEP_SPO2].live = false;
        f->modality[SLEEP_SPO2].quality = 0.f;
    }
    return true;
}
