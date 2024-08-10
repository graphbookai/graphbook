from graphbook.steps.base import Step, AsyncStep

class RemoteReadStep(Step):
    def __init__(self, id, logger):
        super().__init__(id, logger)
        self._remote = None

    def set_remote(self, remote):
        self._remote = remote

    async def run(self, inputs):
        if self._remote is None:
            raise ValueError("Remote is not set")
        return await self._remote.run(inputs)

    async def close(self):
        if self._remote is not None:
            await self._remote.close()

class RemoteWriteStep(Step):
    def __init__(self, id, logger):
        super().__init__(id, logger)
        self._remote = None

    def set_remote(self, remote):
        self._remote = remote

    async def run(self, inputs):
        if self._remote is None:
            raise ValueError("Remote is not set")
        return await self._remote.run(inputs)

    async def close(self):
        if self._remote is not None:
            await self._remote.close()