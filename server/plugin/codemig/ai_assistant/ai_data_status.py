from enum import Enum

# pylint: disable=too-few-public-methods
class AiDataStatus(Enum):
    DONE = 0
    RECEIVING_RESULT = 1
    AI_SUGGESTION_CODE = 2
    AGENT_KEY_INFO = 3
    BACKEND_ERROR = -1
    TIMEOUT = -2
    UNKNOWN_ERROR = -3
    NO_REQUEST_UUID = -4
