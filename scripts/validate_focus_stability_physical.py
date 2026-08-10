from __future__ import annotations

import time

import httpx

from context_anchor.reliable_desktop import StableFocusDesktopBackend


BASE_URL = "http://127.0.0.1:8765"
ORIGIN = BASE_URL
RUNS = 5
TIMEOUT_SECONDS = 90


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def get_status(client: httpx.Client) -> dict:
    response = client.get(f"{BASE_URL}/api/status")
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        fail("/api/status não retornou objeto JSON")
    return payload


def assert_ready(status: dict) -> None:
    if not status.get("central", {}).get("online"):
        fail("Central está offline")
    if not status.get("robot", {}).get("online"):
        fail("Robô local está offline")
    if not status.get("desktop", {}).get("enabled"):
        fail("Controle de desktop está desativado")
    if status.get("emergency", {}).get("active"):
        fail("Parada de emergência está ativa")


def submit_goal(client: httpx.Client, expected_text: str) -> str:
    command = f"Abra um editor de texto e escreva exatamente: {expected_text}"
    response = client.post(
        f"{BASE_URL}/api/tasks",
        headers={"Origin": ORIGIN},
        json={"command": command},
    )
    if response.status_code != 200:
        fail(f"objetivo não foi enfileirado: {response.status_code} {response.text[:300]}")
    task_id = response.json().get("id")
    if not isinstance(task_id, str) or not task_id:
        fail("Task API não retornou task id")
    print(f"INFO: rodada={expected_text[-2:]} task={task_id}")
    return task_id


def wait_for_task(client: httpx.Client, task_id: str) -> dict:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    last_status = "unknown"
    while time.monotonic() < deadline:
        status = get_status(client)
        for task in status.get("tasks", []):
            if isinstance(task, dict) and task.get("id") == task_id:
                last_status = str(task.get("status"))
                if last_status in {"succeeded", "failed"}:
                    return task
        time.sleep(0.8)
    fail(f"timeout aguardando task {task_id}; último estado={last_status}")
    raise AssertionError("unreachable")


def verify_goal_result(task: dict, run_number: int) -> None:
    if task.get("status") != "succeeded":
        fail(
            f"rodada {run_number}/{RUNS} terminou em {task.get('status')}: "
            f"{task.get('error')}"
        )
    result = task.get("result")
    if not isinstance(result, dict):
        fail(f"rodada {run_number}/{RUNS}: succeeded sem result estruturado")
    if result.get("goal_completed") is not True or result.get("verified") is not True:
        fail(
            f"rodada {run_number}/{RUNS}: GoalVerifier não comprovou conclusão "
            f"(goal_completed={result.get('goal_completed')!r}, verified={result.get('verified')!r})"
        )


def verify_readback(expected_text: str, run_number: int) -> None:
    observation = StableFocusDesktopBackend().read_active_text(max_chars=512)
    if observation.get("verified") is not True:
        fail(
            f"rodada {run_number}/{RUNS}: readback AT-SPI não verificado: "
            f"{observation.get('error')}"
        )
    observed = observation.get("text")
    if observed != expected_text:
        fail(
            f"rodada {run_number}/{RUNS}: readback divergente: "
            f"esperado={expected_text!r}, observado={observed!r}"
        )


def main() -> None:
    print("PM-RELIABILITY-FOCUS-001 — smoke físico repetido Linux/X11")
    print(f"Rodadas exigidas: {RUNS}")
    try:
        with httpx.Client(timeout=12.0) as client:
            assert_ready(get_status(client))
            print("PASS: Central, Robô e Desktop prontos; emergência normal")

            completed: list[str] = []
            for run_number in range(1, RUNS + 1):
                assert_ready(get_status(client))
                expected_text = f"Validação de foco estável {run_number:02d}"
                task_id = submit_goal(client, expected_text)
                task = wait_for_task(client, task_id)
                verify_goal_result(task, run_number)
                time.sleep(0.5)
                verify_readback(expected_text, run_number)
                completed.append(task_id)
                print(
                    f"PASS: rodada {run_number}/{RUNS} — GoalVerifier + readback AT-SPI exato"
                )
    except httpx.HTTPError as exc:
        fail(f"falha HTTP ao acessar o Painel local: {exc}")

    print(f"PASS: {len(completed)}/{RUNS} rodadas físicas consecutivas")
    print("PASS_GATE: FOCUS_STABILITY_PHYSICAL")


if __name__ == "__main__":
    main()
