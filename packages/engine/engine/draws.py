"""Banque de tirages communs, indexée par slot et par bloc.

La banque remplace les appels directs aux distributions de
``numpy.random.Generator``. Chaque slot reçoit ses propres uniformes ``U(0,1)``
et normales standard ``Z`` ; une transformation déterministe les convertit
ensuite en valeurs selon la loi demandée. Les deux flux sont générés à la
demande et possèdent des séquences indépendantes : demander seulement ``Z`` ne
consomme pas d'uniformes, et réciproquement.

Invariants :

- le préfixe est stable : ``take(slot, n)[:k] == take(slot, k)`` ;
- les tirages d'un slot ne dépendent ni de l'ordre d'enregistrement, ni des
  autres slots ;
- vider le cache ne change jamais les valeurs, seulement leur temps de calcul.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np

from .errors import EngineError

BLOCK_SIZE = 1024
"""Nombre de runs générés par bloc pour les slots vectoriels (le bruit).

Cette taille fixe la granularité du cache et garantit que les frontières de
blocs ne dépendent pas du nombre total de runs. Un bloc de 256 runs multipliait
par quatre le nombre de générateurs et de concaténations pour le bruit ;
1024 garde un préfixe stable et borne la mémoire par lot.
"""

SCALAR_BLOCK_SIZE = 2_048
"""Taille de bloc des slots scalaires (une valeur par run).

Le runner matérialise de toute façon le tableau complet d'une hypothèse, donc
découper ce tableau en petits blocs n'économise pas de mémoire et multiplie les
générateurs. Des blocs de 2048 runs réduisent la surcharge sans gaspiller trop
de tirages quand `runs` est petit (surface à 200 runs, brouillon à 500 runs).
"""

CACHE_BLOCKS = 16
"""Nombre maximal de blocs conservés en mémoire (LRU).

À 1024 runs et pour un horizon de 36 mois, un bloc de bruit pèse environ
576 Kio : le cache reste ainsi sous 10 Mio. Les tirages restent identiques
quand un bloc est évincé, seule sa régénération coûte du temps.
"""


def slot_identifier(name: str) -> int:
    """Identifiant 64 bits stable dérivé du nom du slot.

    BLAKE2b est utilisé pour que l'identifiant ne dépende ni de l'ordre
    d'insertion, ni du nombre de slots. Deux exécutions produisent donc les
    mêmes tirages pour un même nom.
    """
    digest = hashlib.blake2b(name.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "little")


@dataclass(frozen=True)
class DrawSlot:
    """Slot nommé de la banque de tirages."""

    name: str
    id: int
    width: int = 1
    squeeze: bool = True


class DrawBank:
    """Génère et met en cache des tirages ``U`` et ``Z`` par slot et par bloc."""

    def __init__(
        self,
        seed: int,
        horizon: int,
        block_size: int = BLOCK_SIZE,
        cache_blocks: int = CACHE_BLOCKS,
        scalar_block_size: int = SCALAR_BLOCK_SIZE,
    ) -> None:
        if seed < 0:
            raise ValueError("seed doit être positif ou nul")
        if horizon < 1:
            raise ValueError("horizon doit être strictement positif")
        if block_size < 1:
            raise ValueError("block_size doit être strictement positif")
        if scalar_block_size < 1:
            raise ValueError("scalar_block_size doit être strictement positif")
        if cache_blocks < 1:
            raise ValueError("cache_blocks doit être strictement positif")
        self.seed = seed
        self.horizon = horizon
        self.block_size = block_size
        self.scalar_block_size = scalar_block_size
        self.cache_blocks = cache_blocks
        self._slots: dict[str, DrawSlot] = {}
        self._cache: OrderedDict[tuple[str, int], dict[str, np.ndarray]] = OrderedDict()

    @property
    def slots(self) -> dict[str, DrawSlot]:
        return dict(self._slots)

    @property
    def cached_blocks(self) -> int:
        return len(self._cache)

    def register(self, name: str, *, width: int = 1, squeeze: bool = True) -> DrawSlot:
        """Enregistre un slot et retourne son identifiant stable.

        Réenregistrer le même nom avec la même largeur est idempotent. Une
        largeur différente est une erreur de programmation. ``squeeze=False``
        conserve la forme ``(n, 1)`` pour les slots vectoriels d'une colonne,
        comme le bruit d'un horizon d'un mois.
        """
        if not name:
            raise ValueError("le nom du slot ne peut pas être vide")
        if width < 1:
            raise ValueError("width doit être strictement positif")
        existing = self._slots.get(name)
        if existing is not None:
            if existing.width != width or existing.squeeze != squeeze:
                raise EngineError(
                    f"slot {name!r}: structure incompatible "
                    f"(width={width}, squeeze={squeeze})"
                )
            return existing
        slot = DrawSlot(
            name=name,
            id=slot_identifier(name),
            width=width,
            squeeze=squeeze,
        )
        self._slots[name] = slot
        return slot

    def _block_size(self, slot: DrawSlot) -> int:
        if slot.squeeze and slot.width == 1:
            return self.scalar_block_size
        return self.block_size

    def _stream(
        self,
        slot_name: str,
        block_index: int,
        stream: str,
    ) -> np.ndarray:
        """Retourne un flux ``"u"`` ou ``"z"`` d'un bloc, en le générant si besoin.

        Chaque flux possède sa propre séquence : générer ``U`` seul ne décale
        jamais ``Z``, et inversement. C'est ce qui permet au runner de ne
        demander que le flux utile à la loi (une normale ne consomme que ``Z``,
        une triangulaire que ``U``) sans changer les tirages de base.
        """
        slot = self._slots.get(slot_name)
        if slot is None:
            raise EngineError(f"slot inconnu: {slot_name!r}")
        if block_index < 0:
            raise ValueError("block_index doit être positif ou nul")
        if stream not in ("u", "z"):
            raise ValueError(f"flux inconnu: {stream!r}")

        key = (slot.name, block_index)
        entry = self._cache.get(key)
        if entry is None:
            entry = {}
            self._cache[key] = entry
        else:
            self._cache.move_to_end(key)

        cached = entry.get(stream)
        if cached is not None:
            return cached

        stream_code = 0 if stream == "u" else 1
        sequence = np.random.SeedSequence(
            [self.seed, slot.id, block_index, stream_code]
        )
        rng = np.random.Generator(np.random.PCG64(sequence))
        shape = (self._block_size(slot), slot.width)
        if stream == "u":
            values = rng.random(shape)
        else:
            values = rng.standard_normal(shape)
        if slot.squeeze and slot.width == 1:
            values = np.ascontiguousarray(values[:, 0])

        entry[stream] = values
        if len(self._cache) > self.cache_blocks:
            self._cache.popitem(last=False)
        return values

    def block(self, slot: str, block_index: int) -> tuple[np.ndarray, np.ndarray]:
        """Retourne le couple ``(U, Z)`` d'un bloc complet."""
        return (
            self._stream(slot, block_index, "u"),
            self._stream(slot, block_index, "z"),
        )

    def _range(
        self,
        slot: str,
        start: int,
        stop: int,
        stream: str,
    ) -> np.ndarray:
        registered = self._slots.get(slot)
        if registered is None:
            raise EngineError(f"slot inconnu: {slot!r}")
        if start < 0 or stop < start:
            raise ValueError("plage de tirages invalide")
        if stop == start:
            if registered.squeeze and registered.width == 1:
                return np.empty(0, dtype=np.float64)
            return np.empty((0, registered.width), dtype=np.float64)

        block_size = self._block_size(registered)
        first_block = start // block_size
        last_block = (stop - 1) // block_size
        chunks: list[np.ndarray] = []
        for block_index in range(first_block, last_block + 1):
            values = self._stream(slot, block_index, stream)
            block_start = block_index * block_size
            lower = max(start - block_start, 0)
            upper = min(stop - block_start, block_size)
            chunks.append(values[lower:upper])

        if len(chunks) == 1:
            return chunks[0]
        return np.concatenate(chunks)

    def take_range(
        self,
        slot: str,
        start: int,
        stop: int,
        *,
        uniform: bool = True,
        normal: bool = True,
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        """Retourne les tirages ``[start, stop)`` d'un slot.

        Seuls les blocs couvrant la plage sont générés, et seulement les flux
        demandés. Le résultat est strictement égal à
        ``take(slot, stop, uniform=..., normal=...)[...][start:stop]``.
        """
        uniforms = self._range(slot, start, stop, "u") if uniform else None
        normals = self._range(slot, start, stop, "z") if normal else None
        return uniforms, normals

    def take(
        self,
        slot: str,
        runs: int,
        *,
        uniform: bool = True,
        normal: bool = True,
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        """Retourne les ``runs`` premiers tirages d'un slot."""
        if runs < 0:
            raise ValueError("runs doit être positif ou nul")
        return self.take_range(
            slot,
            0,
            runs,
            uniform=uniform,
            normal=normal,
        )

    def clear(self) -> None:
        self._cache.clear()

    def invalidate_structure(self) -> None:
        """Purge le cache après un changement de structure.

        Les identifiants des slots existants ne changent pas : vider le cache
        provoque une régénération déterministe, jamais des valeurs différentes.
        """
        self.clear()
