"""Message bus module for decoupled channel-agent communication."""

from zero.bus.events import InboundMessage, OutboundMessage
from zero.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
