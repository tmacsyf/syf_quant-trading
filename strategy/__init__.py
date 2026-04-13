"""策略模块"""
from .base import BaseStrategy
from .moving_average import MovingAverageCrossStrategy, MeanReversionStrategy

__all__ = ['BaseStrategy', 'MovingAverageCrossStrategy', 'MeanReversionStrategy']
