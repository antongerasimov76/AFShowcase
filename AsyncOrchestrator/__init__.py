
import logging
from datetime import timedelta
from multiprocessing import context
import azure.durable_functions as df

def orchestrator_function(context: df.DurableOrchestrationContext):
    data = context.get_input() or {}
    action = data.get("action")
    payload = data.get("payload")

    if not context.is_replaying:
        logging.info(f"[Orchestrator] action={action}")

    retry = df.RetryOptions(timedelta(seconds=10), 3)
    result = yield context.call_activity_with_retry("ExecuteAction", retry, {"action": action, "payload": payload})

    if not context.is_replaying:
        logging.info("[Orchestrator] activity completed")
    return result

# ОБЯЗАТЕЛЬНО:
main = df.Orchestrator.create(orchestrator_function)
