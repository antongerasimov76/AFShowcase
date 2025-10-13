import logging
import importlib
from datetime import datetime
import azure.durable_functions as df

def main(context: df.DurableActivityContext):
    started = datetime.utcnow()
    req = context.get_input() or {}
    action = req.get("action")
    payload = req.get("payload") or {}

    if not action:
        return {"error": "Action is required"}

    module_name = f"shared_code.handlers.{action}"  # ищем файл handlers/<Action>.py
    try:
        module = importlib.import_module(module_name)
        handler = getattr(module, "run")
    except Exception as e:
        return {"error": f"Handler not found for action '{action}' ({module_name}). {e}"}

    try:
        logging.info(f"[ExecuteAction] {action} started")
        result = handler(payload)
        elapsed = int((datetime.utcnow() - started).total_seconds() * 1000)
        logging.info(f"[ExecuteAction] {action} finished in {elapsed} ms")
        return {"action": action, "result": result, "durationMs": elapsed}
    except Exception as e:
        logging.exception(f"[ExecuteAction] {action} failed")
        return {"action": action, "error": str(e)}
