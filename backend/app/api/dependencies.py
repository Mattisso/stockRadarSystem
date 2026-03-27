"""Typed dependency helpers for app.state services."""

from fastapi import Request


def get_broker(request: Request):
    return request.app.state.broker


def get_cache(request: Request):
    return request.app.state.cache


def get_state_machine(request: Request):
    return request.app.state.state_machine


def get_trade_executor(request: Request):
    return request.app.state.trade_executor


def get_runtime(request: Request):
    return request.app.state.runtime
