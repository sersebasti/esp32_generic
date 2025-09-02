# adc_scope.py  (solo counts, niente volt)
from machine import ADC, Pin
import time, ujson, math

ADC_PIN = 34
ADC_ATTEN_DB = 11     # non influisce sui "counts_rms" come scala assoluta, ma evita saturazione
ADC_WIDTH_BITS = 12
_ADC = None
_ADC_MAX = (1 << ADC_WIDTH_BITS) - 1

def _init():
    global _ADC
    if _ADC: return
    a = ADC(Pin(ADC_PIN))
    if   ADC_ATTEN_DB == 0:  a.atten(ADC.ATTN_0DB)
    elif ADC_ATTEN_DB == 2:  a.atten(ADC.ATTN_2_5DB)
    elif ADC_ATTEN_DB == 6:  a.atten(ADC.ATTN_6DB)
    else:                    a.atten(ADC.ATTN_11DB)
    if   ADC_WIDTH_BITS == 9:  a.width(ADC.WIDTH_9BIT)
    elif ADC_WIDTH_BITS == 10: a.width(ADC.WIDTH_10BIT)
    elif ADC_WIDTH_BITS == 11: a.width(ADC.WIDTH_11BIT)
    else:                      a.width(ADC.WIDTH_12BIT)
    _ADC = a

def _read_count():
    # piccola media su 4 per ridurre jitter
    s = 0
    for _ in range(4):
        s += _ADC.read()
    return s >> 2

def sample_counts(n=512, sample_rate_hz=4000):
    _init()
    n = max(32, min(int(n), 4096))
    sr = max(200, min(int(sample_rate_hz), 20000))
    dt_us = int(1_000_000 / sr)
    arr = []
    for _ in range(n):
        arr.append(_read_count())
        time.sleep_us(dt_us)
    return arr, sr

def stats_counts(arr):
    n = len(arr)
    s = sum(arr)
    mean = s / n
    acc = 0.0
    for v in arr:
        dv = v - mean
        acc += dv*dv
    rms = math.sqrt(acc / n)   # RMS dell'AC (mean rimosso)
    return mean, rms

def json_dump_counts(n=512, sample_rate_hz=4000):
    arr, sr = sample_counts(n, sample_rate_hz)
    mean, rms = stats_counts(arr)
    return ujson.dumps({
        "ok": True,
        "n": len(arr),
        "sample_rate_hz": sr,
        "counts": arr,
        "counts_mean": round(mean, 2),
        "counts_rms": round(rms, 2)
    })
