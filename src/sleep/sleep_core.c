#include "sleep_core.h"
#include <math.h>
#include <string.h>

bool sleep_ring_push(sleep_ring_t *r, const sleep_frame_t *f)
{
    if (r->count == SLEEP_RING_CAPACITY) { r->dropped++; return false; }
    r->frames[r->write] = *f;
    r->write = (r->write + 1u) % SLEEP_RING_CAPACITY;
    r->count++;
    return true;
}
bool sleep_ring_pop(sleep_ring_t *r, sleep_frame_t *f)
{
    if (!r->count) return false;
    *f = r->frames[r->read];
    r->read = (r->read + 1u) % SLEEP_RING_CAPACITY;
    r->count--;
    return true;
}
static bool usable(const sleep_frame_t *f, unsigned m)
{
    const sleep_modality_t *v = &f->modality[m];
    return v->present && v->live && isfinite(v->value) && isfinite(v->quality)
        && v->quality >= .5f && v->quality <= 1.f
        && v->timestamp_ms <= f->timestamp_ms
        && f->timestamp_ms - v->timestamp_ms <= SLEEP_MAX_GAP_MS
        && (m == SLEEP_SPO2 ? (v->value >= 50.f && v->value <= 100.f) : v->value >= 0.f);
}
static void transition(sleep_session_t *s, sleep_state_t state, uint64_t now)
{
    s->state = state;
    s->state_since_ms = now;
    s->positive_count = s->negative_count = 0;
}
void sleep_session_init(sleep_session_t *s)
{
    memset(s, 0, sizeof(*s));
    s->prediction = SLEEP_UNCERTAIN;
    s->summary.minimum_spo2 = NAN;
    s->trigger_armed = true;
}
static void account_time(sleep_session_t *s, uint64_t now)
{
    if (!s->started) return;
    uint64_t dt = now - s->last_ms;
    s->summary.monitoring_ms += dt;
    if (s->previous_valid && dt <= SLEEP_MAX_GAP_MS) {
        s->summary.valid_ms += dt;
        s->summary.quality_ms += s->previous_quality * (double)dt;
        if (s->previous_spo2 < 90.f) s->summary.below_90_ms += dt;
        if (s->baseline_ready && s->previous_spo2 < s->baseline_spo2)
            s->summary.oxygen_burden_pct_s += (s->baseline_spo2-s->previous_spo2)*(double)dt/1000.;
    } else s->summary.missing_ms += dt;
}
static void finish_event(sleep_session_t *s, uint64_t end, bool accept)
{
    sleep_event_t *e = &s->active_event;
    e->end_ms = end;
    e->duration_s = (float)(end-e->start_ms)/1000.f;
    e->spo2_drop = fmaxf(0.f, e->spo2_before-e->spo2_min);
    if (accept && e->duration_s >= 10.f) {
        e->event_id = ++s->summary.event_count;
        s->summary.longest_event_s = fmaxf(s->summary.longest_event_s, e->duration_s);
        s->summary.sum_spo2_drop += e->spo2_drop;
        s->last_event = *e;
        s->event_ready = true;
    } else s->summary.rejected_events++;
}
static void evidence(sleep_event_t *e, const sleep_frame_t *f, float quality)
{
    e->model_score = fmaxf(e->model_score, f->event_probability);
    e->signal_quality = fminf(e->signal_quality, quality);
    e->spo2_min = fminf(e->spo2_min, f->modality[SLEEP_SPO2].value);
    e->resp_effort_score = f->modality[SLEEP_RESP].value;
    e->motion_present = usable(f, SLEEP_MOTION);
    e->audio_present = usable(f, SLEEP_AUDIO);
    e->movement_score = e->motion_present ? f->modality[SLEEP_MOTION].value : NAN;
    e->audio_score = e->audio_present ? f->modality[SLEEP_AUDIO].value : NAN;
}
sleep_error_t sleep_session_step(sleep_session_t *s, const sleep_frame_t *f)
{
    if (s->state == SLEEP_SESSION_END) return SLEEP_ERR_FINISHED;
    if (s->started && f->timestamp_ms <= s->last_ms) {
        s->summary.timestamp_errors++;
        return SLEEP_ERR_TIMESTAMP;
    }
    s->event_ready = false;
    bool gap = s->started && f->timestamp_ms-s->last_ms > SLEEP_MAX_GAP_MS;
    bool good = usable(f, SLEEP_SPO2) && usable(f, SLEEP_RESP);
    float spo2 = f->modality[SLEEP_SPO2].value, resp = f->modality[SLEEP_RESP].value;
    float quality = good ? fminf(f->modality[SLEEP_SPO2].quality, f->modality[SLEEP_RESP].quality) : 0.f;
    account_time(s, f->timestamp_ms);
    s->last_ms = f->timestamp_ms;
    s->started = true;
    s->previous_valid = good;
    s->previous_spo2 = spo2;
    s->previous_quality = quality;
    if (usable(f, SLEEP_SPO2)) {
        if (!isfinite(s->summary.minimum_spo2) || spo2 < s->summary.minimum_spo2)
            s->summary.minimum_spo2 = spo2;
    }
    if (!good || gap) {
        if (s->state == SLEEP_EVENT_ACTIVE) finish_event(s, f->timestamp_ms, false);
        if (!s->baseline_ready) s->baseline_count = 0;
        transition(s, SLEEP_SENSOR_FAULT, f->timestamp_ms);
        s->prediction = SLEEP_FAULT;
        return SLEEP_OK;
    }
    if (s->state == SLEEP_IDLE || s->state == SLEEP_SENSOR_FAULT)
        transition(s, SLEEP_MONITORING_LOW, f->timestamp_ms);
    if (!s->baseline_ready) {
        /* Stable pre-session calibration; this does not establish clinical normality. */
        if (s->baseline_count && (fabsf(spo2-s->baseline_spo2) > 1.f
                || fabsf(resp-s->baseline_resp) > .1f*s->baseline_resp)) s->baseline_count = 0;
        if (resp <= .0001f) { s->prediction = SLEEP_UNCERTAIN; return SLEEP_OK; }
        s->baseline_count++;
        if (s->baseline_count == 1) { s->baseline_spo2 = spo2; s->baseline_resp = resp; }
        else {
            s->baseline_spo2 += (spo2-s->baseline_spo2)/(float)s->baseline_count;
            s->baseline_resp += (resp-s->baseline_resp)/(float)s->baseline_count;
        }
        s->baseline_ready = s->baseline_count >= SLEEP_BASELINE_SAMPLES;
        s->prediction = SLEEP_UNCERTAIN;
        return SLEEP_OK;
    }
    bool model_ok = f->inference_valid && isfinite(f->event_probability)
        && f->event_probability >= 0.f && f->event_probability <= 1.f;
    bool trigger = spo2 <= s->baseline_spo2-3.f || resp <= .5f*s->baseline_resp;
    if (model_ok && f->event_probability >= .7f) trigger = true;
    if (!trigger) s->trigger_armed = true;
    if (s->state == SLEEP_MONITORING_LOW && trigger && s->trigger_armed) {
        s->trigger_armed = false;
        transition(s, SLEEP_MONITORING_HIGH, f->timestamp_ms);
    }
    if (!model_ok) {
        s->summary.inference_errors++;
        s->prediction = SLEEP_UNCERTAIN;
        if (s->state == SLEEP_EVENT_ACTIVE) {
            finish_event(s, f->timestamp_ms, false);
            transition(s, SLEEP_RECOVERY, f->timestamp_ms);
        }
        s->positive_count = s->negative_count = 0;
        if ((s->state == SLEEP_MONITORING_HIGH || s->state == SLEEP_RECOVERY)
                && f->timestamp_ms-s->state_since_ms >= 15000u)
            transition(s, SLEEP_MONITORING_LOW, f->timestamp_ms);
        return SLEEP_ERR_MODEL;
    }
    s->prediction = f->event_probability >= .3f ? SLEEP_UNCERTAIN : SLEEP_NORMAL;
    if (s->state == SLEEP_MONITORING_HIGH) {
        s->prediction = SLEEP_UNCERTAIN;
        if (f->event_probability >= .7f) {
            if (!s->positive_count) {
                s->candidate_ms = f->timestamp_ms;
                memset(&s->active_event, 0, sizeof(s->active_event));
                s->active_event.start_ms = s->candidate_ms;
                s->active_event.spo2_before = s->baseline_spo2;
                s->active_event.spo2_min = spo2;
                s->active_event.signal_quality = quality;
            }
            evidence(&s->active_event, f, quality);
            if (++s->positive_count >= 3u) {
                transition(s, SLEEP_EVENT_ACTIVE, f->timestamp_ms);
                s->prediction = SLEEP_SUSPICIOUS_EVENT;
            }
        } else s->positive_count = 0;
        if (s->state == SLEEP_MONITORING_HIGH && f->timestamp_ms-s->state_since_ms >= 15000u)
            transition(s, SLEEP_RECOVERY, f->timestamp_ms);
    } else if (s->state == SLEEP_EVENT_ACTIVE) {
        s->prediction = SLEEP_SUSPICIOUS_EVENT;
        if (f->event_probability < .3f) {
            if (!s->negative_count) s->end_candidate_ms = f->timestamp_ms;
            if (++s->negative_count >= 3u) {
                finish_event(s, s->end_candidate_ms, true);
                transition(s, SLEEP_RECOVERY, f->timestamp_ms);
                s->prediction = SLEEP_NORMAL;
            }
        } else {
            s->negative_count = 0;
            evidence(&s->active_event, f, quality);
        }
    } else if (s->state == SLEEP_RECOVERY && f->timestamp_ms-s->state_since_ms >= 5000u) {
        transition(s, SLEEP_MONITORING_LOW, f->timestamp_ms);
    }
    /* A sustained unresolved trigger must not become a confident normal. */
    if (trigger && s->prediction == SLEEP_NORMAL) s->prediction = SLEEP_UNCERTAIN;
    return SLEEP_OK;
}
sleep_error_t sleep_session_end(sleep_session_t *s, uint64_t now)
{
    if (s->state == SLEEP_SESSION_END) return SLEEP_ERR_FINISHED;
    if (s->started && now < s->last_ms) return SLEEP_ERR_TIMESTAMP;
    account_time(s, now);
    if (s->state == SLEEP_EVENT_ACTIVE)
        finish_event(s, s->negative_count ? s->end_candidate_ms : now,
                     now-s->last_ms <= SLEEP_MAX_GAP_MS);
    transition(s, SLEEP_SESSION_END, now);
    return SLEEP_OK;
}
float sleep_events_per_hour(const sleep_session_t *s)
{
    return s->summary.valid_ms ? (float)s->summary.event_count*3600000.f/(float)s->summary.valid_ms : 0.f;
}
sleep_triage_t sleep_triage(const sleep_session_t *s)
{
    /* Research demonstration thresholds only. Never a clinical AHI/diagnosis. */
    if (!s->baseline_ready || !s->summary.valid_ms || s->summary.inference_errors
            || (double)s->summary.valid_ms < .8*(double)s->summary.monitoring_ms)
        return SLEEP_TRIAGE_INSUFFICIENT;
    float frequency = sleep_events_per_hour(s);
    if (frequency >= 15.f) return SLEEP_TRIAGE_HIGH;
    if (frequency >= 5.f) return SLEEP_TRIAGE_MODERATE;
    return SLEEP_TRIAGE_LOW;
}
const char *sleep_state_name(sleep_state_t state)
{
    static const char *const names[] = {"IDLE", "MONITORING_LOW", "MONITORING_HIGH",
        "EVENT_ACTIVE", "RECOVERY", "SENSOR_FAULT", "SESSION_END"};
    return (unsigned)state < 7u ? names[state] : "INVALID";
}
const char *sleep_prediction_name(sleep_prediction_t prediction)
{
    static const char *const names[] = {"NORMAL", "SUSPICIOUS_EVENT", "UNCERTAIN", "SENSOR_FAULT"};
    return (unsigned)prediction < 4u ? names[prediction] : "INVALID";
}
