"""Resilience & Lifecycle Review Lens — Fault-tolerance, zombie handle prevention, and self-healing guard."""

from skybrain.review.lenses.base import Category, ReviewLens


class ResilienceLens(ReviewLens):
    """Analyzes source code for runtime resilience, lifecycle decoupling, and self-healing.

    Focus areas:
      1. Decoupled Lifecycle: Ensuring handles to external/OS/network processes (Binders, Sockets,
         Connection Pools, Hardware Proxies) are never cached indefinitely without death/disconnection guards.
      2. Immediate Invalidation (Fail-Clean): Immediate teardown and nullification of broken handles
         upon error, disconnection, or unbind, preventing zombie proxy lockups (e.g. Error 11 DeadProxy).
      3. Atomic Session Scoping: Acquiring external hardware or IPC sessions on-demand and releasing
         them immediately upon completion rather than keeping dangling background bindings.
      4. Transparent Self-Healing: Automatically retrying transient connection drops (IPC disconnect,
         TCP reset, stale socket) with backoff before propagating raw failures to the user.
      5. Resource Concurrency & Ownership: Preventing multi-tenant collisions on singular OS resources
         within the same process (e.g. concurrent speech recognizer / TTS session limits).
    """

    @property
    def name(self) -> str:
        return "Resilience"

    @property
    def category(self) -> Category:
        return Category.RESILIENCE

    @property
    def system_prompt(self) -> str:
        return (
            "You are a Principal Resilience & Reliability Engineer specializing in fault tolerance, "
            "distributed systems, and mobile/backend lifecycle decoupling.\n\n"
            "Rigidly evaluate the source code against these 5 Resilience & Lifecycle Invariants:\n\n"
            "1. **Decoupled Lifecycle Guard (No Zombie Handles)**:\n"
            "   - Does the code assume that an external IPC service, OS binder, socket, or remote connection "
            "     will stay alive just because the local application process is running?\n"
            "   - Look for references to remote proxies (e.g., Android SpeechRecognizer, TextToSpeech, "
            "     InputConnection, Bluetooth, DB Connection Pool, WebSocket) stored in persistent member variables "
            "     or singletons without health checks or reconnect logic.\n\n"
            "2. **Immediate Invalidation (Fail-Clean & Zero Stale Proxy)**:\n"
            "   - When an error, disconnection, or unbind callback occurs, does the code immediately "
            "     destroy, unbind, and nullify the underlying handle?\n"
            "   - Anti-pattern: Only updating UI status flags to 'IDLE' or 'ERROR' while leaving the dead "
            "     handle/binder in memory to fail repeatedly on subsequent calls (e.g., Error 11 loops).\n\n"
            "3. **Atomic Session Scoping & Prompt Cleanup**:\n"
            "   - Are hardware resources, audio records, or native sessions held open longer than necessary?\n"
            "   - The code must release external resources as soon as a discrete operation completes "
            "     (Fresh-on-Start / Clean-on-Finish) rather than hoarding them across user idle periods.\n\n"
            "4. **Transparent Self-Healing (Resilience to Transient Drops)**:\n"
            "   - Does the code implement at least one clean automatic retry/reconnection when a recoverable "
            "     disconnection error occurs (e.g. ERROR_SERVER_DISCONNECTED, BrokenPipe, StaleConnection)?\n"
            "   - Or does it abruptly fail and push the error burden onto the user?\n\n"
            "5. **Resource Concurrency & Single Ownership**:\n"
            "   - Does the code guard against multiple components within the same process independently "
            "     opening competing sessions to a constrained system service (e.g. OS-imposed limit on "
            "     concurrent SpeechRecognizer or AudioTrack sessions)?\n\n"
            "Severity Guidelines:\n"
            "- CRITICAL: Persistent zombie handle causing permanent lockup after remote disconnect\n"
            "- HIGH: Missing cleanup on error paths leaving dangling background hardware/IPC bindings\n"
            "- MEDIUM: Lack of transient auto-recovery for common network/IPC drops\n"
            "- LOW: Minor lifecycle listener unregistering delays\n\n"
            "Be ruthlessly rigorous: cite exact line numbers, detail the exact failure/disconnect scenario, "
            "and provide the authentic, robust self-healing correction."
        )
