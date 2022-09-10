from enum import Enum
from typing import List, TypeAlias
from dotenv import load_dotenv
from urllib import parse
import os

load_dotenv()

class LogTypes(Enum):
    FATAL = 1
    ERROR = 2
    WARNING = 3
    INFO = 4
    DEBUG = 5
    TRACE = 6


LT: TypeAlias = LogTypes
default_log_type: LT = LT(int(os.getenv("LOG_TYPE_NUM", "5")))
DLT: TypeAlias = default_log_type


class ConsoleColor(Enum):
    BLACK = '\033[30m'  # (文字)黒
    RED = '\033[31m'  # (文字)赤
    GREEN = '\033[32m'  # (文字)緑
    YELLOW = '\033[33m'  # (文字)黄
    BLUE = '\033[34m'  # (文字)青
    MAGENTA = '\033[35m'  # (文字)マゼンタ
    CYAN = '\033[36m'  # (文字)シアン
    WHITE = '\033[37m'  # (文字)白
    COLOR_DEFAULT = '\033[39m'  # 文字色をデフォルトに戻す
    BOLD = '\033[1m'  # 太字
    UNDERLINE = '\033[4m'  # 下線
    INVISIBLE = '\033[08m'  # 不可視
    REVERCE = '\033[07m'  # 文字色と背景色を反転
    BG_BLACK = '\033[40m'  # (背景)黒
    BG_RED = '\033[41m'  # (背景)赤
    BG_GREEN = '\033[42m'  # (背景)緑
    BG_YELLOW = '\033[43m'  # (背景)黄
    BG_BLUE = '\033[44m'  # (背景)青
    BG_MAGENTA = '\033[45m'  # (背景)マゼンタ
    BG_CYAN = '\033[46m'  # (背景)シアン
    BG_WHITE = '\033[47m'  # (背景)白
    BG_DEFAULT = '\033[49m'  # 背景色をデフォルトに戻す
    RESET = '\033[0m'  # 全てリセット


CC: TypeAlias = ConsoleColor


class LogColor(Enum):
    FATAL = CC.RED
    ERROR = CC.RED
    WARNING = CC.YELLOW
    INFO = CC.CYAN
    DEBUG = CC.GREEN
    TRACE = CC.WHITE


LC: TypeAlias = LogColor

def urlencode(url) -> str:
    return parse.quote(str(url), safe="")


def color_text(text: str, color: CC) -> str:
    return f"{color.value}{text}{CC.RESET.value}"


def format_text(text: str, formats: List[CC]):
    return f"{''.join(map(lambda format: format.value, formats))}{text}{CC.RESET.value}" if formats else text


def bold_text(text: str) -> str:
    return f"{CC.BOLD.value}{text}{CC.RESET.value}"


class Logger:
    def __init__(self, log_type: LT = DLT):
        self.log_type = log_type

    def log(self, log_type: LT, message: str, *, custom_formats: List[CC] = None) -> None:
        if log_type.value <= self.log_type.value:
            print_text = format_text(
                color_text(
                    f"{log_format(log_type)}: {message}".replace(
                        "\n", f"\n{log_format(log_type)}: "),
                    LC[log_type.name].value
                ), custom_formats
            )
            print(print_text)


def log_format(log_type: LT):
    return f"[ {log_type.name:7} ]"