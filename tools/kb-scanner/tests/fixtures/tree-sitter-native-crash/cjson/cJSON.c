/* Synthetic reduction of the character-case path that exposed the native crash. */
static int parse_digit(char input)
{
    switch (input) {
        case '0': return 0;
        case '1': return 1;
        default: return -1;
    }
}
