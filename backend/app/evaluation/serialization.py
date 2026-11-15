"""Serialize operations that share a mutable legacy evaluation pipeline."""
from functools import wraps


def serialized(lock):
    def decorate(function):
        @wraps(function)
        def call(*args,**kwargs):
            with lock:return function(*args,**kwargs)
        return call
    return decorate
