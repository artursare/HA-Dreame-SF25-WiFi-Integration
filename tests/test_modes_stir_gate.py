"""Safety regressions for SF25 virtual programs; no device or HA installation needed."""
import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'dreame_sf25'
package = types.ModuleType('dreame_sf25')
package.__path__ = [str(ROOT)]
sys.modules['dreame_sf25'] = package
for name in ('homeassistant', 'homeassistant.helpers'):
    module = types.ModuleType(name)
    module.__path__ = []
    sys.modules[name] = module
core = types.ModuleType('homeassistant.core')
core.HomeAssistant = object
core.callback = lambda fn: fn
sys.modules[core.__name__] = core
exceptions = types.ModuleType('homeassistant.exceptions')
exceptions.HomeAssistantError = type('HomeAssistantError', (Exception,), {})
sys.modules[exceptions.__name__] = exceptions
event = types.ModuleType('homeassistant.helpers.event')
event.async_call_later = lambda *args, **kwargs: lambda: None
event.async_track_time_change = lambda *args, **kwargs: lambda: None
sys.modules[event.__name__] = event
storage = types.ModuleType('homeassistant.helpers.storage')
class Store:
    def __init__(self, *args): pass
    async def async_save(self, data): pass
    async def async_load(self): return {}
storage.Store = Store
sys.modules[storage.__name__] = storage
for name in ('const', 'modes'):
    spec = importlib.util.spec_from_file_location(f'dreame_sf25.{name}', ROOT / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

const = sys.modules['dreame_sf25.const']
Modes = sys.modules['dreame_sf25.modes'].DreameSF25Modes

class StirGateTests(unittest.IsolatedAsyncioTestCase):
    """Remover debe ser una puerta que vuelve a cerrarse, no un pestillo."""

    def setUp(self):
        self.started = []
        self.hass = types.SimpleNamespace(
            async_add_executor_job=self.executor,
            async_create_task=lambda coro: asyncio.create_task(coro),
        )
        self.coordinator = types.SimpleNamespace(
            data={const.PROP_PROGRAM: const.PROGRAM_OPTIONS['idle']},
            client=types.SimpleNamespace(set_property=lambda *a: None),
            entry=types.SimpleNamespace(options={
                const.CONF_AUTO_MODES: True,
                const.CONF_VIRTUAL_MODES: True,
            }),
            async_request_refresh=AsyncMock(),
            async_update_listeners=Mock(),
        )
        self.modes = Modes(self.hass, self.coordinator, 'test-entry')
        # Registrar los arranques sin tocar el aparato ni temporizadores.
        async def fake_start(mode):
            self.started.append((mode, self.modes.lid_count))
            self.modes.virtual_mode = mode
        self.modes.async_start_virtual = fake_start

    async def executor(self, fn, *args):
        return fn(*args)

    async def close_lid(self):
        """Un ciclo apertura-cierre completo."""
        self.modes.virtual_mode = None
        await self.modes._async_lid_closed(const.PROGRAM_OPTIONS['idle'])

    async def test_stir_fires_once_per_threshold_not_every_close(self):
        for _ in range(12):
            await self.close_lid()
        self.assertEqual([c for _, c in self.started], [3, 6, 9, 12])

    async def test_lid_count_keeps_climbing_as_the_fill_signal(self):
        for _ in range(12):
            await self.close_lid()
        self.assertEqual(self.modes.lid_count, 12)

    async def test_threshold_is_configurable(self):
        self.coordinator.entry.options[const.CONF_STIR_THRESHOLD] = 5
        for _ in range(12):
            await self.close_lid()
        self.assertEqual([c for _, c in self.started], [5, 10])

    async def test_auto_stir_can_be_disabled_without_touching_compact(self):
        self.coordinator.entry.options[const.CONF_AUTO_STIR] = False
        for _ in range(12):
            await self.close_lid()
        self.assertEqual(self.started, [])
        self.assertEqual(self.modes.lid_count, 12)

    async def test_completed_program_resets_counter_and_anchor(self):
        for _ in range(4):
            await self.close_lid()
        self.assertEqual(len(self.started), 1)
        await self.modes.async_reset_counter()
        self.assertEqual(self.modes.lid_count, 0)
        for _ in range(3):
            await self.close_lid()
        self.assertEqual([c for _, c in self.started], [3, 3])

    async def test_anchor_cannot_exceed_a_hand_set_counter(self):
        for _ in range(6):
            await self.close_lid()
        self.assertEqual(len(self.started), 2)
        # Bajar el contador a mano arrastra el ancla con el, asi que hacen
        # falta otras 3 aperturas (contador 4) y no se dispara de inmediato.
        await self.modes.async_set_lid_count(1)
        for _ in range(2):
            await self.close_lid()
        self.assertEqual([c for _, c in self.started], [3, 6])
        await self.close_lid()
        self.assertEqual([c for _, c in self.started], [3, 6, 4])


if __name__ == '__main__':
    unittest.main()
