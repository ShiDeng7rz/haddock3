"""Greeting messages for the command line clients."""

import os
import random
import sys
from datetime import datetime
from functools import partial
from typing import Sequence

from haddock import contact_us, version


international_good_byes = [
    "Adéu-siau",
    "Agur",
    "Até logo",
    "Au revoir",
    "Ciao",
    "Dovidenia",
    "Good bye",
    "Tot ziens",
    "La revedere",
    "Adiós",
    "Do pobachennya",
]


def get_initial_greeting() -> str:
    """Create initial greeting message."""
    now = datetime.now().replace(second=0, microsecond=0)
    python_version = sys.version
    message = (
        f"""{os.linesep}"""
        f"""##############################################{os.linesep}"""
        f"""#                                            #{os.linesep}"""
        f"""#                 HADDOCK 3                  #{os.linesep}"""
        f"""#                                            #{os.linesep}"""
        f"""##############################################{os.linesep}"""
        f"""{os.linesep}"""
        f"""Starting HADDOCK {version} on {now}{os.linesep}"""
        f"""{os.linesep}"""
        f"""Python {python_version}{os.linesep}"""
    )
    return message


def get_greetings(
    options: Sequence[str], how_many: int = 3, sep: str = " ", exclamation: str = "!"
) -> str:
    """Get greeting messages."""
    n = how_many % len(options)
    return sep.join(s + exclamation for s in random.sample(options, k=n))


def get_adieu() -> str:
    """Create end-run greeting message."""
    end = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    bye = get_goodbye_greetings()
    message = f"Finished at {end}. {bye}"
    return message


def get_goodbye_help() -> str:
    """Create good-bye message with help."""
    end = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    bye = get_goodbye_greetings()
    message = f"Finished at {end}. For any help contact us at {contact_us}. {bye}."
    return message


get_goodbye_greetings = partial(get_greetings, international_good_byes)
