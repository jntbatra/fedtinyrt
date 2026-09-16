#include <assert.h>
#include <math.h>
#include <stdio.h>
#include "../../src/sleep/sleep_core.h"
#include "../../src/sleep/sleep_replay.h"

static sleep_frame_t frame(unsigned i)
{
    sleep_frame_t f;
    assert(sleep_replay_frame(i % SLEEP_REPLAY_SECONDS, (uint64_t)i*1000u, &f));
    return f;
}
static void calibrate(sleep_session_t *s)
{
    sleep_session_init(s);
    for (unsigned i = 0; i < 40u; i++) {
        sleep_frame_t f = frame(i);
        assert(sleep_session_step(s, &f) == SLEEP_OK);
    }
    assert(s->baseline_ready);
    assert(fabsf(s->baseline_spo2-97.f) < .001f);
}
int main(void)
{
    sleep_session_t s;
    sleep_session_init(&s);
    bool seen[7] = {false};
    for (unsigned i = 0; i < SLEEP_REPLAY_SECONDS; i++) {
        sleep_frame_t f = frame(i);
        assert(sleep_session_step(&s, &f) == SLEEP_OK);
        seen[s.state] = true;
    }
    assert(sleep_session_end(&s, 100000u) == SLEEP_OK);
    assert(s.summary.event_count == 1u);
    assert(s.last_event.duration_s == 20.f);
    assert(s.last_event.spo2_drop == 8.f);
    assert(s.summary.monitoring_ms == 100000u);
    assert(s.summary.valid_ms == 95000u);
    assert(s.summary.missing_ms == 5000u);
    assert(s.summary.below_90_ms == 20000u);
    assert(s.summary.oxygen_burden_pct_s == 160.);
    assert(seen[SLEEP_MONITORING_LOW] && seen[SLEEP_MONITORING_HIGH]
           && seen[SLEEP_EVENT_ACTIVE] && seen[SLEEP_RECOVERY] && seen[SLEEP_SENSOR_FAULT]);
    assert(sleep_session_end(&s, 101000u) == SLEEP_ERR_FINISHED);

    sleep_ring_t ring = {0};
    sleep_frame_t f = frame(0), out;
    for (unsigned i = 0; i < SLEEP_RING_CAPACITY; i++) {
        f.timestamp_ms = i;
        assert(sleep_ring_push(&ring, &f));
    }
    assert(!sleep_ring_push(&ring, &f) && ring.dropped == 1u);
    for (unsigned i = 0; i < SLEEP_RING_CAPACITY; i++) {
        assert(sleep_ring_pop(&ring, &out));
        assert(out.timestamp_ms == i);
    }
    assert(!sleep_ring_pop(&ring, &out));
    assert(sleep_ring_push(&ring, &f) && sleep_ring_pop(&ring, &out));

    calibrate(&s);
    f = frame(40); f.modality[SLEEP_SPO2].present = false;
    sleep_session_step(&s, &f);
    assert(s.prediction == SLEEP_FAULT);
    f = frame(41); f.modality[SLEEP_SPO2].timestamp_ms = 0;
    sleep_session_step(&s, &f);
    assert(s.prediction == SLEEP_FAULT);
    f = frame(42); f.modality[SLEEP_RESP].quality = NAN;
    sleep_session_step(&s, &f);
    assert(s.prediction == SLEEP_FAULT);
    uint64_t valid = s.summary.valid_ms;
    assert(sleep_session_step(&s, &f) == SLEEP_ERR_TIMESTAMP);
    assert(s.summary.valid_ms == valid);

    calibrate(&s);
    for (unsigned i = 40; i < 60; i++) {
        f = frame(i); f.inference_valid = false;
        assert(sleep_session_step(&s, &f) == SLEEP_ERR_MODEL);
        assert(s.prediction == SLEEP_UNCERTAIN);
    }
    assert(s.summary.event_count == 0u && sleep_triage(&s) == SLEEP_TRIAGE_INSUFFICIENT);

    /* Same absolute respiration has different baseline-relative trigger behavior. */
    calibrate(&s);
    s.baseline_resp = .3f;
    f = frame(40); f.modality[SLEEP_SPO2].value = 97.f; f.event_probability = .1f;
    sleep_session_step(&s, &f);
    assert(s.state == SLEEP_MONITORING_LOW);
    calibrate(&s);
    sleep_session_step(&s, &f);
    assert(s.state == SLEEP_MONITORING_HIGH);

    calibrate(&s);
    f = frame(40); f.modality[SLEEP_SPO2].value = 97.f;
    f.modality[SLEEP_RESP].value = 1.f; f.event_probability = .5f;
    sleep_session_step(&s, &f);
    assert(s.prediction == SLEEP_UNCERTAIN);
    f.timestamp_ms += 1000u; f.event_probability = .9f;
    sleep_session_step(&s, &f);
    assert(s.state == SLEEP_MONITORING_HIGH);

    /* Short detections are rejected; acquisition gaps terminate active events. */
    calibrate(&s);
    for (unsigned i = 40; i < 47; i++) {
        f = frame(i);
        if (i >= 44) f.event_probability = .1f;
        sleep_session_step(&s, &f);
    }
    assert(s.summary.event_count == 0u && s.summary.rejected_events == 1u);
    calibrate(&s);
    for (unsigned i = 40; i < 44; i++) { f = frame(i); sleep_session_step(&s, &f); }
    f = frame(50); sleep_session_step(&s, &f);
    assert(s.state == SLEEP_SENSOR_FAULT && s.summary.event_count == 0u);

    /* A persistent trigger rejected by inference cannot repeatedly start HIGH. */
    calibrate(&s);
    unsigned enters = 0;
    for (unsigned i = 40; i < 100; i++) {
        f = frame(i); f.modality[SLEEP_SPO2].value = 89.f;
        f.modality[SLEEP_SPO2].present = f.modality[SLEEP_SPO2].live = true;
        f.modality[SLEEP_SPO2].quality = 1.f;
        f.event_probability = .1f;
        sleep_state_t before = s.state;
        sleep_session_step(&s, &f);
        if (before != SLEEP_MONITORING_HIGH && s.state == SLEEP_MONITORING_HIGH) enters++;
        assert(s.prediction != SLEEP_NORMAL);
    }
    assert(enters == 1u);
    puts("PASS: synthetic replay, ring overflow, quality, timing, baseline, faults, recovery, triage");
    return 0;
}
