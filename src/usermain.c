#include <tk/tkernel.h>
#include <tm/tmonitor.h>

EXPORT INT usermain(void)
{
    tm_putstring((UB*)"FedTinyRT starting...\n");

    tk_slp_tsk(TMO_FEVR);

    return 0;
}
