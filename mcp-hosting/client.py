import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def predict(model_name: str, id_value: int, overrides: dict | None = None):
    async with streamablehttp_client("http://localhost:8000/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(
                "predict_from_id",
                arguments={"model_name": model_name, "id_value": id_value, "overrides": overrides}
            )
            return res

print(asyncio.run(predict("classifier1", 12345, {"date": "2026-01-15"})))
