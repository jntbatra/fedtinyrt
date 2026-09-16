#include <tk/tkernel.h>
#include <tm/tmonitor.h>
#include "sleep/sleep_core.h"
#include "sleep/sleep_replay.h"

/* Keep the existing FSP -> hal_entry -> kernel -> usermain boot path.
 * CPU0 replay only. No real sensor or trained-model backend is implied. */
LOCAL sleep_ring_t replay_ring;
LOCAL sleep_session_t session;
LOCAL bool acquisition_finished;
LOCAL uint64_t acquisition_end_ms;
LOCAL uint32_t missed_releases;
LOCAL uint64_t acquisition_stack[256];
LOCAL uint64_t processing_stack[512];

LOCAL bool monotonic_ms(uint64_t *now)
{
    SYSTIM time;
    if (tk_get_otm(&time) < E_OK) return false;
    *now = ((uint64_t)(uint32_t)time.hi << 32) | time.lo;
    return true;
}

LOCAL void acquisition_task(INT stacd, void *exinf)
{
    (void)stacd; (void)exinf;
    uint64_t now = 0, next = 0;
    if (!monotonic_ms(&next)) {
        tk_dis_dsp(); acquisition_finished = true; tk_ena_dsp();
        tk_ext_tsk();
        return;
    }
    for (uint32_t i = 0; i < SLEEP_REPLAY_SECONDS; i++) {
        if (!monotonic_ms(&now)) break;
        if (now < next) {
            if (tk_dly_tsk((RELTIM)(next-now)) < E_OK || !monotonic_ms(&now)) break;
        }
        if (now >= next+1000u) {
            uint64_t skipped = (now-next)/1000u;
            if (skipped >= SLEEP_REPLAY_SECONDS-i) {
                tk_dis_dsp(); missed_releases += SLEEP_REPLAY_SECONDS-i; tk_ena_dsp();
                break;
            }
            i += (uint32_t)skipped;
            next += skipped*1000u;
            tk_dis_dsp(); missed_releases += (uint32_t)skipped; tk_ena_dsp();
        }
        sleep_frame_t frame;
        sleep_replay_frame(i, now, &frame);
        tk_dis_dsp();
        sleep_ring_push(&replay_ring, &frame);
        tk_ena_dsp();
        next += 1000u;
    }
    if (monotonic_ms(&now) && now < next) {
        tk_dly_tsk((RELTIM)(next-now));
        monotonic_ms(&now);
    }
    tk_dis_dsp();
    acquisition_end_ms = now;
    acquisition_finished = true;
    tk_ena_dsp();
    tk_ext_tsk();
}

LOCAL void processing_task(INT stacd, void *exinf)
{
    (void)stacd; (void)exinf;
    sleep_state_t last_state = SLEEP_SESSION_END;
    sleep_prediction_t last_prediction = SLEEP_FAULT;
    while (1) {
        sleep_frame_t frame;
        bool have_frame, finished;
        uint64_t end_ms;
        uint32_t dropped, missed;
        tk_dis_dsp();
        have_frame = sleep_ring_pop(&replay_ring, &frame);
        finished = acquisition_finished;
        end_ms = acquisition_end_ms;
        dropped = replay_ring.dropped;
        missed = missed_releases;
        tk_ena_dsp();
        if (have_frame) {
            sleep_session_step(&session, &frame);
            if (session.state != last_state || session.prediction != last_prediction) {
                tm_printf((UB*)"[SYNTHETIC] mode=%s status=%s baseline_ready=%d\n",
                          sleep_state_name(session.state), sleep_prediction_name(session.prediction),
                          (INT)session.baseline_ready);
                last_state = session.state;
                last_prediction = session.prediction;
            }
            if (session.event_ready) {
                tm_printf((UB*)"[SYNTHETIC] event=%d duration_s=%d spo2_drop=%d\n",
                          (INT)session.last_event.event_id, (INT)session.last_event.duration_s,
                          (INT)session.last_event.spo2_drop);
            }
        } else if (finished) {
            sleep_session_end(&session, end_ms < session.last_ms ? session.last_ms : end_ms);
            tm_printf((UB*)"[SYNTHETIC] SESSION_END valid_s=%d missing_s=%d events=%d dropped=%d missed_releases=%d\n",
                      (INT)(session.summary.valid_ms/1000u), (INT)(session.summary.missing_ms/1000u),
                      (INT)session.summary.event_count, (INT)dropped, (INT)missed);
            static const char *const triage[] = {"LOW", "MODERATE", "HIGH", "INSUFFICIENT_DATA"};
            tm_printf((UB*)"[SYNTHETIC] research_triage=%s (scripted demo; no diagnosis)\n", triage[sleep_triage(&session)]);
            tk_ext_tsk();
            return;
        } else tk_dly_tsk(10);
    }
}

LOCAL T_CTSK acquisition_config = {
    .itskpri = 8, .stksz = sizeof(acquisition_stack), .task = acquisition_task,
    .tskatr = TA_HLNG | TA_RNG3 | TA_USERBUF, .bufptr = acquisition_stack
};
LOCAL T_CTSK processing_config = {
    .itskpri = 12, .stksz = sizeof(processing_stack), .task = processing_task,
    .tskatr = TA_HLNG | TA_RNG3 | TA_USERBUF, .bufptr = processing_stack
};

EXPORT INT usermain(void)
{
    tm_putstring((UB*)"FedTinyRT starting...\n");
    tm_putstring((UB*)"FedTinyRT Sleep: SYNTHETIC replay, scripted scores, model=NONE, fixture=v1\n");
    sleep_session_init(&session);
    ID sensor_id = tk_cre_tsk(&acquisition_config);
    if (sensor_id < E_OK) {
        tm_putstring((UB*)"Sleep startup failed: acquisition task\n");
        return sensor_id;
    }
    ID process_id = tk_cre_tsk(&processing_config);
    if (process_id < E_OK) {
        tk_del_tsk(sensor_id);
        tm_putstring((UB*)"Sleep startup failed: processing task\n");
        return process_id;
    }
    ER result = tk_sta_tsk(process_id, 0);
    if (result < E_OK) {
        tk_del_tsk(process_id); tk_del_tsk(sensor_id);
        tm_putstring((UB*)"Sleep startup failed: start processing\n");
        return result;
    }
    result = tk_sta_tsk(sensor_id, 0);
    if (result < E_OK) {
        tk_ter_tsk(process_id); tk_del_tsk(process_id); tk_del_tsk(sensor_id);
        tm_putstring((UB*)"Sleep startup failed: start acquisition\n");
        return result;
    }
    tk_slp_tsk(TMO_FEVR);

    return 0;
}
