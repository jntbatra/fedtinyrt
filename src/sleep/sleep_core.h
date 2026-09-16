#ifndef FEDTINYRT_SLEEP_CORE_H
#define FEDTINYRT_SLEEP_CORE_H
#include <stdbool.h>
#include <stdint.h>

#define SLEEP_MODALITIES 4u
#define SLEEP_RING_CAPACITY 16u
#define SLEEP_BASELINE_SAMPLES 30u
#define SLEEP_MAX_GAP_MS 2000u
enum { SLEEP_SPO2, SLEEP_RESP, SLEEP_MOTION, SLEEP_AUDIO };
typedef enum { SLEEP_IDLE, SLEEP_MONITORING_LOW, SLEEP_MONITORING_HIGH,
    SLEEP_EVENT_ACTIVE, SLEEP_RECOVERY, SLEEP_SENSOR_FAULT, SLEEP_SESSION_END } sleep_state_t;
typedef enum { SLEEP_NORMAL, SLEEP_SUSPICIOUS_EVENT, SLEEP_UNCERTAIN,
    SLEEP_FAULT } sleep_prediction_t;
typedef enum { SLEEP_TRIAGE_LOW, SLEEP_TRIAGE_MODERATE, SLEEP_TRIAGE_HIGH,
    SLEEP_TRIAGE_INSUFFICIENT } sleep_triage_t;
typedef enum { SLEEP_OK, SLEEP_ERR_TIMESTAMP, SLEEP_ERR_MODEL,
    SLEEP_ERR_FINISHED } sleep_error_t;

/* Values are synchronized scalar summaries, not waveform samples. Raw sensor
 * drivers and per-modality rings will be added after bench validation. */
typedef struct {
    float value, quality;
    uint64_t timestamp_ms;
    bool present, live;
} sleep_modality_t;
typedef struct {
    uint64_t timestamp_ms;
    sleep_modality_t modality[SLEEP_MODALITIES];
    float event_probability;
    bool inference_valid;
} sleep_frame_t;
typedef struct {
    sleep_frame_t frames[SLEEP_RING_CAPACITY];
    uint32_t read, write, count, dropped;
} sleep_ring_t;
/* Caller must serialize push/pop; usermain uses short dispatch-disabled copies. */
bool sleep_ring_push(sleep_ring_t *ring, const sleep_frame_t *frame);
bool sleep_ring_pop(sleep_ring_t *ring, sleep_frame_t *frame);

typedef struct {
    uint32_t event_id;
    uint64_t start_ms, end_ms;
    float duration_s, model_score, signal_quality;
    float spo2_before, spo2_min, spo2_drop, resp_effort_score;
    float movement_score, audio_score;
    bool motion_present, audio_present;
} sleep_event_t;
typedef struct {
    uint64_t monitoring_ms, valid_ms, missing_ms, below_90_ms;
    uint32_t event_count, rejected_events, inference_errors, timestamp_errors;
    float longest_event_s, minimum_spo2, sum_spo2_drop;
    double oxygen_burden_pct_s, quality_ms;
} sleep_summary_t;
typedef struct {
    sleep_state_t state;
    sleep_prediction_t prediction;
    sleep_summary_t summary;
    sleep_event_t active_event, last_event;
    uint64_t last_ms, state_since_ms, candidate_ms, end_candidate_ms;
    uint32_t baseline_count, positive_count, negative_count;
    float baseline_spo2, baseline_resp, previous_spo2, previous_quality;
    bool started, previous_valid, baseline_ready, trigger_armed, event_ready;
} sleep_session_t;

void sleep_session_init(sleep_session_t *session);
sleep_error_t sleep_session_step(sleep_session_t *session, const sleep_frame_t *frame);
sleep_error_t sleep_session_end(sleep_session_t *session, uint64_t timestamp_ms);
float sleep_events_per_hour(const sleep_session_t *session);
sleep_triage_t sleep_triage(const sleep_session_t *session);
const char *sleep_state_name(sleep_state_t state);
const char *sleep_prediction_name(sleep_prediction_t prediction);
#endif
