from typing import List, Optional, Dict, Any, Callable, Union, TypedDict
from copy import copy
from dataclasses import dataclass
from .base_memory import BaseMemory
from .message import BaseMessage


class SlidingMemoryHandlers(TypedDict, total=False):
    """Type definition for SlidingMemory handlers."""

    removal_selector: Callable[
        [List[BaseMessage]], Union[BaseMessage, List[BaseMessage]]
    ]


@dataclass
class SlidingMemoryConfig:
    """Configuration for SlidingMemory."""

    size: int
    handlers: Optional[SlidingMemoryHandlers] = None


class SlidingMemory(BaseMemory):
    """Memory implementation using a sliding window approach."""

    def __init__(self, config: SlidingMemoryConfig):
        """Initialize SlidingMemory with given configuration.

        Args:
            config: Configuration including window size and optional handlers
        """
        self._messages: List[BaseMessage] = []
        self.config = config

        # Set default handlers if not provided
        if self.config.handlers is None:
            self.config.handlers = {}

        # Set default removal selector if not provided
        if "removal_selector" not in self.config.handlers:
            self.config.handlers["removal_selector"] = lambda messages: [messages[0]]

    @property
    def messages(self) -> List[BaseMessage]:
        """Get list of stored messages."""
        return self._messages

    def _is_overflow(self, additional_messages: int = 1) -> bool:
        """Check if adding messages would cause overflow."""
        return len(self._messages) + additional_messages > self.config.size

    def _ensure_range(self, index: int, min_val: int, max_val: int) -> int:
        """Ensure index is within the specified range."""
        return max(min_val, min(index, max_val))

    async def add(self, message: BaseMessage, index: Optional[int] = None) -> None:
        """Add a message to memory, managing window size.

        Args:
            message: Message to add
            index: Optional position to insert message

        Raises:
            MemoryFatalError: If removal selector fails to prevent overflow
        """
        # Check for overflow
        if self._is_overflow():
            # Get messages to remove using removal selector
            to_remove = self.config.handlers["removal_selector"](self._messages)
            if not isinstance(to_remove, list):
                to_remove = [to_remove]

            # Remove selected messages
            for msg in to_remove:
                try:
                    msg_index = self._messages.index(msg)
                    self._messages.pop(msg_index)
                except ValueError:
                    raise MemoryError(
                        "Cannot delete non existing message.",
                        context={"message": msg, "messages": self._messages},
                    )

            # Check if we still have overflow
            if self._is_overflow():
                raise MemoryError(
                    "Custom memory removalSelector did not return enough messages. Memory overflow has occurred."
                )

        # Add new message
        if index is None:
            index = len(self._messages)
        index = self._ensure_range(index, 0, len(self._messages))
        self._messages.insert(index, message)

    async def delete(self, message: BaseMessage) -> bool:
        """Delete a message from memory.

        Args:
            message: Message to delete

        Returns:
            bool: True if message was found and deleted
        """
        try:
            self._messages.remove(message)
            return True
        except ValueError:
            return False

    def reset(self) -> None:
        """Clear all messages from memory."""
        self._messages.clear()

    def create_snapshot(self) -> Dict[str, Any]:
        """Create a serializable snapshot of current state."""
        return {
            "config": {"size": self.config.size, "handlers": self.config.handlers},
            "messages": copy(self._messages),
        }

    def load_snapshot(self, state: Dict[str, Any]) -> None:
        """Restore state from a snapshot."""
        self.config = SlidingMemoryConfig(
            size=state["config"]["size"], handlers=state["config"]["handlers"]
        )
        self._messages = copy(state["messages"])