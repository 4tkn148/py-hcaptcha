from ..challenges import Challenge
from .exceptions import *
from collections import Mapping
from hashlib import sha1
from typing import Union
import random
import redis

class Solver:
    def __init__(
        self,
        database: Union[redis.Redis, Mapping],
        min_answers: int = 3
        ):
        """Used for solving challenges using a bruteforce technique.
        
        :param database: :class:`Redis` or :class:`Mapping` object to be used for storing tile IDs and counts.
        :param min_answers: minimum amount of answers to be submitted for a challenge."""
        self._database = database
        self._min_answers = min_answers

    def solve(self, challenge: Challenge) -> str:
        """Attempt to solve challenge. Returns token if successful."""
        if challenge.token:
            return challenge.token

        if challenge.mode != "image_label_binary":
            raise UnsupportedChallenge(
                f"Unsupported challenge mode: {challenge.mode}")

        prefixes = [
            "Please click each image containing a ",
            "Please click each image containing an ",
        ]
        prefix = None
        for _prefix in prefixes:
            if challenge.question["en"].startswith(_prefix):
                prefix = _prefix
                break
        if not prefix:
            raise UnsupportedChallenge(
                f"Unsupported challenge question: {challenge.question['en']}")
        
        variation = challenge.question["en"] \
            .replace(prefix, "").rstrip(".").lower()
        
        for tile in challenge.tiles:
            image = tile.get_image(raw=True)
            image_hash = sha1(image).hexdigest()
            tile.custom_id = f"{variation}|{image_hash}"
            tile.score = self._get_tile_score(tile)
            tile.selected = False

        challenge.tiles.sort(
            key=lambda tile: tile.score or random.uniform(0, 0.9),
            reverse=True)
        
        for index in range(max(
                self._min_answers,
                len([1 for tile in challenge.tiles if tile.score >= 1])
            )):
            tile = challenge.tiles[index]
            tile.selected = True
            challenge.answer(tile)

        challenge.submit()

        for tile in challenge.tiles:
            if not tile.selected: continue
            self._incr_tile_score(tile, 1)
        
        return challenge.token

    def _get_tile_score(self, tile):
        if isinstance(self._database, redis.Redis):
            return int(self._database.get(tile.custom_id) or 0)

        elif isinstance(self._database, Mapping):
            return self._database.get(tile.custom_id, 0)

    def _incr_tile_score(self, tile, incr_by):
        if isinstance(self._database, redis.Redis):
            self._database.incrby(tile.custom_id, incr_by)

        elif isinstance(self._database, Mapping):
            value = self._database.get(tile.custom_id, 0)
            self._database[tile.custom_id] = value + incr_by