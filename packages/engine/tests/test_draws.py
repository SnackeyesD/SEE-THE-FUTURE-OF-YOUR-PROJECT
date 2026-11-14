from __future__ import annotations

import numpy as np
import pytest

from engine import EngineError
from engine.draws import BLOCK_SIZE, DrawBank, slot_identifier


def test_prefix_is_stable_across_block_boundaries() -> None:
    full = DrawBank(seed=42, horizon=36)
    full.register("hyp:unit_price")
    reference_u, reference_z = full.take("hyp:unit_price", 1_000)

    for size in (250, 256, 257, 500, 1_000):
        bank = DrawBank(seed=42, horizon=36)
        bank.register("hyp:unit_price")
        uniform, normal = bank.take("hyp:unit_price", size)
        np.testing.assert_array_equal(uniform, reference_u[:size])
        np.testing.assert_array_equal(normal, reference_z[:size])


def test_take_range_matches_take_slice() -> None:
    bank = DrawBank(seed=7, horizon=12)
    bank.register("noise", width=12)
    uniform, normal = bank.take("noise", 1_000)
    for start, stop in ((0, 1), (1, 255), (255, 257), (250, 700), (999, 1_000)):
        range_u, range_z = bank.take_range("noise", start, stop)
        np.testing.assert_array_equal(range_u, uniform[start:stop])
        np.testing.assert_array_equal(range_z, normal[start:stop])


def test_slot_draws_do_not_depend_on_registration_order() -> None:
    first = DrawBank(seed=11, horizon=4)
    first.register("hyp:a")
    first.register("hyp:b")
    second = DrawBank(seed=11, horizon=4)
    second.register("hyp:b")
    second.register("hyp:a")

    np.testing.assert_array_equal(first.take("hyp:a", 300)[1], second.take("hyp:a", 300)[1])
    np.testing.assert_array_equal(first.take("hyp:b", 300)[1], second.take("hyp:b", 300)[1])


def test_adding_a_slot_does_not_change_existing_draws() -> None:
    before = DrawBank(seed=11, horizon=4)
    before.register("hyp:unit_price")
    reference = before.take("hyp:unit_price", 500)

    after = DrawBank(seed=11, horizon=4)
    after.register("hyp:unit_price")
    after.register("event:ev1:active")
    after.register("noise", width=4)

    np.testing.assert_array_equal(after.take("hyp:unit_price", 500)[0], reference[0])
    np.testing.assert_array_equal(after.take("hyp:unit_price", 500)[1], reference[1])


def test_cache_can_be_cleared_without_changing_values() -> None:
    bank = DrawBank(seed=3, horizon=6)
    bank.register("noise", width=6)
    reference = bank.take("noise", 600)
    bank.clear()
    assert bank.cached_blocks == 0
    np.testing.assert_array_equal(bank.take("noise", 600)[1], reference[1])


def test_cache_is_bounded() -> None:
    bank = DrawBank(seed=3, horizon=6, cache_blocks=2)
    bank.register("noise", width=6)
    for block in range(10):
        bank.block("noise", block)
    assert bank.cached_blocks == 2


def test_slot_identifier_is_stable_and_name_based() -> None:
    assert slot_identifier("noise") == slot_identifier("noise")
    assert slot_identifier("noise") != slot_identifier("hyp:unit_price")
    slot = DrawBank(seed=1, horizon=1).register("hyp:unit_price")
    assert slot.id == slot_identifier("hyp:unit_price")


def test_registered_slot_width_is_enforced() -> None:
    bank = DrawBank(seed=1, horizon=4)
    bank.register("noise", width=4)
    with pytest.raises(EngineError):
        bank.register("noise", width=3)


def test_unknown_slot_is_an_error() -> None:
    bank = DrawBank(seed=1, horizon=4)
    with pytest.raises(EngineError):
        bank.take("missing", 10)


def test_empty_range_keeps_the_shape() -> None:
    bank = DrawBank(seed=1, horizon=4)
    bank.register("hyp:a")
    bank.register("noise", width=4)
    uniform, normal = bank.take("noise", 0)
    assert uniform.shape == (0, 4)
    assert normal.shape == (0, 4)
    uniform, normal = bank.take("hyp:a", 0)
    assert uniform.shape == (0,)
    assert normal.shape == (0,)


def test_streams_are_independent_and_lazy() -> None:
    only_normal = DrawBank(seed=13, horizon=4)
    only_normal.register("hyp:unit_price")
    _, normal_first = only_normal.take("hyp:unit_price", 700, uniform=False)

    uniform_first = DrawBank(seed=13, horizon=4)
    uniform_first.register("hyp:unit_price")
    uniform_first.take("hyp:unit_price", 700, uniform=True, normal=False)
    _, normal_after_uniform = uniform_first.take(
        "hyp:unit_price", 700, uniform=False, normal=True
    )

    np.testing.assert_array_equal(normal_first, normal_after_uniform)


def test_unrequested_stream_is_not_returned() -> None:
    bank = DrawBank(seed=4, horizon=3)
    bank.register("hyp:unit_price")
    uniform, normal = bank.take("hyp:unit_price", 300, normal=False)
    assert uniform is not None
    assert normal is None

    uniform, normal = bank.take("hyp:unit_price", 300, uniform=False)
    assert uniform is None
    assert normal is not None


def test_noise_can_be_taken_without_uniforms() -> None:
    full = DrawBank(seed=21, horizon=6)
    full.register("noise", width=6, squeeze=False)
    _, reference = full.take("noise", 1_500)

    normal_only = DrawBank(seed=21, horizon=6)
    normal_only.register("noise", width=6, squeeze=False)
    uniform, normal = normal_only.take_range(
        "noise", 0, 1_500, uniform=False
    )
    assert uniform is None
    np.testing.assert_array_equal(normal, reference)

    start, stop = 900, 1_400
    _, chunk = normal_only.take_range(
        "noise", start, stop, uniform=False
    )
    np.testing.assert_array_equal(chunk, reference[start:stop])


def test_block_size_is_documented_constant() -> None:
    assert BLOCK_SIZE == 1_024


def test_prefix_is_stable_around_the_noise_block_boundary() -> None:
    reference_bank = DrawBank(seed=99, horizon=12)
    reference_bank.register("noise", width=12)
    reference = reference_bank.take("noise", 2_048)

    for size in (1_023, 1_024, 1_025, 1_500, 2_048):
        bank = DrawBank(seed=99, horizon=12)
        bank.register("noise", width=12)
        uniform, normal = bank.take("noise", size)
        np.testing.assert_array_equal(uniform, reference[0][:size])
        np.testing.assert_array_equal(normal, reference[1][:size])


def test_prefix_is_stable_around_the_scalar_block_boundary() -> None:
    reference_bank = DrawBank(seed=101, horizon=4)
    reference_bank.register("hyp:unit_price")
    reference = reference_bank.take("hyp:unit_price", 2_049)

    for size in (2_047, 2_048, 2_049):
        bank = DrawBank(seed=101, horizon=4)
        bank.register("hyp:unit_price")
        _, normal = bank.take("hyp:unit_price", size)
        np.testing.assert_array_equal(normal, reference[1][:size])
