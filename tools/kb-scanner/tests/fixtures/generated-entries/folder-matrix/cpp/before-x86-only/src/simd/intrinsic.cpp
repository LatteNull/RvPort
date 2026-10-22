long intrinsic_case(long value) {
  return _InterlockedExchange_HLEAcquire(&value, 1);
}

