import json
import logging
import azure.functions as func
import azure.durable_functions as df
#1
async def main(req: func.HttpRequest, starter: str) -> func.HttpResponse:
    logging.info("[Start] GetZeroAnswerDurable called")
    client = df.DurableOrchestrationClient(starter)

    try:
        body = req.get_json()
    except ValueError:
        body = {}

    # Клиент НЕ передаёт action — мы задаём его внутри
    orch_input = {"action": "GetZeroAnswer", "payload": body}
    instance_id = await client.start_new("AsyncOrchestrator", None, orch_input)
    logging.info(f"[Start] orchestration started id={instance_id}")

    return client.create_check_status_response(req, instance_id)
