"""Chat channels module with plugin architecture."""

from zero.channels.base import BaseChannel
from zero.channels.manager import ChannelManager

__all__ = ["BaseChannel", "ChannelManager"]
