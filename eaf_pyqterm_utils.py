# Copyright (C) 2023 by Mumulhl <mumulhl@duck.com>
# SPDX-License-Identifier: GPL-3.0-or-later


# https://github.com/emacs-eaf/eaf-pdf-viewer/blob/021a4eae8f64b886ac97c10c1417816ed86f4a95/eaf_pdf_utils.py#L38
def generate_random_key(count: int, letters: str) -> list[str]:
    import math
    import random

    key_list = []
    key_len = 1 if count == 1 else math.ceil(math.log(count) / math.log(len(letters)))
    while count > 0:
        key = "".join(random.choices(letters, k=key_len))
        if key not in key_list:
            key_list.append(key)
            count -= 1
    return key_list


import re

LINK_PATTERN = re.compile(r"(https?://(?:[\w-]+\.)+[\w-]+(?:/[\w/?%&=-]*)?)")
WORD_PATTERN = re.compile(r"[\s,\._()=*\"'\[\]/-]")
SYMBOL_PATTERN = re.compile(r"\s")


def match_link(text: str) -> (dict[int, str], int):
    start = 0
    count = 0
    links = {}
    while True:
        match_pattern = LINK_PATTERN.search(text, start)
        if not match_pattern:
            break
        else:
            count += 1
            links[match_pattern.start()] = match_pattern.group()
            start = match_pattern.end()
    return links, count


def get_regexp(thing: str):
    if thing == "word":
        return WORD_PATTERN
    elif thing == "symbol":
        return SYMBOL_PATTERN
