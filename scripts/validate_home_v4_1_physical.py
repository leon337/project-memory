from __future__ import annotations

import sys
import time

import httpx

from context_anchor.desktop import PyAutoGuiDesktopBackend


BASE_URL = "http://127.0.0.1:8765"
ORIGIN = BASE_URL
COMMAND = "Abra um editor de texto e escreva exatamente: Validação real número 1"
EXPECTED_TEXT = "Validação real número 1"
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


def verify_security_surface(client: httpx.Client) -> None:
    rejected = client.post(
        f"{BASE_URL}/api/robot/stop",
        headers={"Origin": "https://evil.example"},
    )
    if rejected.status_code != 403:
        fail(f"mutação cross-origin deveria retornar 403, retornou {rejected.status_code}")

    status = get_status(client)
    for task in status.get("tasks", []):
        if isinstance(task, dict) and (
            "lease_token" in task or "lease_expires_at" in task
        ):
            fail("/api/status expôs dados internos de lease")


def verify_conversation(client: httpx.Client) -> None:
    response = client.post(
        f"{BASE_URL}/api/conversation",
        headers={"Origin": ORIGIN},
        json={"message": "Em qual projeto você está? Responda apenas o nome do projeto."},
    )
    if response.status_code != 200:
        fail(f"conversa não respondeu com sucesso: {response.status_code} {response.text[:300]}")
    payload = response.json()
    reply = str(payload.get("reply", ""))
    provider = payload.get("provider")
    model = payload.get("model")
    context_version = payload.get("context_version")
    if "project-memory" not in reply.casefold():
        fail(f"IA não identificou project-memory na resposta: {reply[:300]}")
    if not provider or not model or not context_version:
        fail("conversa não informou provider/model/context_version reais")
    print(f"PASS: conversa isolada respondeu via {provider}/{model}, contexto={context_version}")


def submit_goal(client: httpx.Client) -> str:
    response = client.post(
        f"{BASE_URL}/api/tasks",
        headers={"Origin": ORIGIN},
        json={"command": COMMAND},
    )
    if response.status_code != 200:
        fail(f"objetivo não foi enfileirado: {response.status_code} {response.text[:300]}")
    task_id = response.json().get("id")
    if not isinstance(task_id, str) or not task_id:
        fail("Task API não retornou task id")
    print(f"INFO: task criada: {task_id}")
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


def verify_goal_result(task: dict) -> None:
    if task.get("status") != "succeeded":
        fail(f"task terminou em {task.get('status')}: {task.get('error')}")
    result = task.get("result")
    if not isinstance(result, dict):
        fail("task succeeded sem result estruturado")
    if result.get("goal_completed") is not True:
        fail("result.goal_completed não é true")
    if result.get("verified") is not True:
        fail("result.verified não é true")
    print("PASS: GoalVerifier autorizou succeeded com verified=true")


def verify_physical_readback() -> None:
    observation = PyAutoGuiDesktopBackend().read_active_text(max_chars=512)
    if observation.get("verified") is not True:
        fail(f"readback AT-SPI não foi verificado: {observation.get('error')}")
    observed = observation.get("text")
    if observed != EXPECTED_TEXT:
        fail(f"readback divergente: esperado={EXPECTED_TEXT!r}, observado={observed!r}")
    print(f"PASS: readback AT-SPI exato: {observed!r}")


def main() -> None:
    print("PM-HOME-IMPLEMENT-001 — validação física Home V4.1")
    try:
        with httpx.Client(timeout=12.0) as client:
            status = get_status(client)
            assert_ready(status)
            print("PASS: Central, Robô e Desktop prontos; emergência normal")
            verify_security_surface(client)
            print("PASS: fronteira Host/Origin/status validada")
            verify_conversation(client)
            task_id = submit_goal(client)
            task = wait_for_task(client, task_id)
            verify_goal_result(task)
            time.sleep(0.5)
            verify_physical_readback()
    except httpx.HTTPError as exc:
        fail(f"falha HTTP ao acessar o Painel local: {exc}")

    print("PASS_GATE: HOME_V4_1_PHYSICAL")


if __name__ == "__main__":
    main()
