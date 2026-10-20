import asyncio
from app.adapters.base import ICommunicationAdapter, AdapterCapability
from app.adapters.simulation import simulation_adapter
from app.adapters.motorola import MotorolaRadioAdapter
from app.adapters.starv import StarVRadioAdapter
from app.adapters.sdr import SdrResearchAdapter


def test_all_adapters_satisfy_contract():
    async def run():
        adapters = [
            simulation_adapter,
            MotorolaRadioAdapter(),
            StarVRadioAdapter(),
            SdrResearchAdapter(),
        ]

        for adapter in adapters:
            assert isinstance(adapter, ICommunicationAdapter)
            meta = adapter.get_metadata()
            assert meta.adapter_id is not None
            assert meta.name is not None
            assert meta.vendor is not None

            caps = adapter.get_capabilities()
            assert isinstance(caps, list)

            health = await adapter.check_health()
            assert health.state is not None
            assert health.summary is not None

    asyncio.run(run())
