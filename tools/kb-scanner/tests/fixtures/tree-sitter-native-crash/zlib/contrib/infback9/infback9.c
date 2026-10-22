/* Synthetic reduction of the unbound state-case path that exposed the native crash. */
#define TYPE 1
#define DONE 2

static int inflate9_step(int state)
{
    switch (state) {
        case TYPE: return 1;
        case DONE: return 0;
        default: return -1;
    }
}
