/* Synthetic reduction of the numeric-case path that exposed the native crash. */
static int option_for(unsigned selector)
{
    switch (selector) {
        case 0: return 10;
        case 1: return 20;
        case 2: return 30;
        default: return 0;
    }
}
