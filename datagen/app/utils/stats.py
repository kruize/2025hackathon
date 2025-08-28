import math
from typing import List

def percentile(arr: List[float], p: float) -> float:
    if not arr:
        return float("nan")
    arr_sorted = sorted(arr)
    k = (len(arr_sorted) - 1) * (p / 100.0)
    f = math.floor(k); c = math.ceil(k)
    if f == c:
        return arr_sorted[int(k)]
    d0 = arr_sorted[f] * (c - k)
    d1 = arr_sorted[c] * (k - f)
    return d0 + d1
