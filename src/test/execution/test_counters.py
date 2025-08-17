'''
Created on Aug 17, 2025

@author: immanueltrummer
'''
from tdb.execution.counters import LLMCounters, TdbCounters


def test_addition():
    counters1 = TdbCounters()
    counters2 = TdbCounters()
    counters3 = counters1 + counters2
    assert isinstance(counters3, TdbCounters)
    assert counters3.processed_tasks == 0
    assert counters3.unprocessed_tasks == 0