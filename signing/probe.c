#include <stdio.h>
int marker_probe_value(void);
int main(void) {
    if (marker_probe_value() != 27194) return 1;
    puts("marker-signing-probe: same-team library loaded");
    return 0;
}
