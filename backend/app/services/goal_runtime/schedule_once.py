from __future__ import annotations


async def run_schedule_once(app_state) -> dict:
    gpus = await app_state.agent.get_all_gpus()
    gpus = app_state.import_context.filter_gpus(gpus)
    processes = await app_state.agent.get_processes()
    processes = app_state.import_context.filter_processes(processes)
    if not gpus:
        return {"success": False, "error": "当前导入范围内无法获取 GPU 数据"}

    rule_actions = await app_state.scheduler.run_rules(gpus, processes)
    rule_results = await app_state.scheduler.execute_actions(rule_actions) if rule_actions else []
    budget_actions = await app_state.scheduler.run_budget_schedule(gpus, processes)
    budget_results = await app_state.scheduler.execute_actions(budget_actions) if budget_actions else []
    ai_strategy = await app_state.scheduler.run_ai_schedule(gpus, processes)
    ai_actions = ai_strategy.get("actions", []) if ai_strategy else []
    ai_results = await app_state.scheduler.execute_actions(ai_actions) if ai_actions else []
    return {
        "success": True,
        "rule_results": rule_results,
        "budget_results": budget_results,
        "ai_results": ai_results,
    }
