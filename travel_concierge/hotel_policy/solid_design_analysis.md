# SOLID Design Analysis: Plugin vs Per-Agent Callbacks for Hotel Policy Injection

Saved from chat session `efd962aa-a7b3-4240-aefd-e9d0bc852040`  
Date: 2026-05-23

---

## User

> two designs, one is what we have in plugin, the other one is add callback function along with the policy files and add callback to each agent. appliy the SOLID design principle to it and evaluate these two designs

---

## Assistant — First SOLID Evaluation

Great framework to apply. Let's evaluate both designs against each SOLID principle rigorously.

---

### The Two Designs

**Design A — Current (Plugin)**
```
App(plugins=[HotelPolicyPlugin()])
  └── before_model_callback: reads agent_name → injects general + specific policy
```

**Design B — Per-agent Callbacks**
```
booking_agent  = Agent(..., before_agent_callback=booking_policy_callback)
planning_agent = Agent(..., before_agent_callback=planning_policy_callback)
...  ×18 agents
```

---

### S — Single Responsibility Principle
> *A module should have one reason to change.*

**Design A (Plugin)**
- `HotelPolicyPlugin` has one reason to change: policy content or how policy is injected.
- Agent files have one reason to change: agent capabilities.
- ✅ Clean separation.

**Design B (Callbacks)**
- Agent files now change for *two* reasons: capability changes AND policy changes.
- The callback function lives inside or next to the agent, coupling two concerns.
- ❌ Agents have mixed responsibilities.

**Winner: A**

---

### O — Open/Closed Principle
> *Open for extension, closed for modification.*

**Design A (Plugin)**
- Add a new agent → no modification needed; general policy applies automatically.
- Add a new policy rule → edit the `.md` file only, no code changes.
- Add a second plugin (e.g., `CompliancePlugin`) → register alongside `HotelPolicyPlugin`, zero agent-level changes.
- ✅ Fully closed to modification when extending.

**Design B (Callbacks)**
- Add a new agent → must write and wire a new callback. Existing code must be *modified*.
- Change a shared policy rule → must touch every callback that references it.
- ❌ Every extension requires modifying existing agent definitions.

**Winner: A**

---

### L — Liskov Substitution Principle
> *Subtypes must be substitutable for their base types without altering correctness.*

This principle applies to the plugin's base class contract.

**Design A (Plugin)**
- `HotelPolicyPlugin` extends `BasePlugin` and overrides `before_model_callback`.
- It returns `None` (pass-through), never short-circuits unexpectedly.
- It does not change the meaning of `before_model_callback` — it extends it.
- ✅ Substitutable. You could swap it for a `NullPolicyPlugin(BasePlugin)` in tests with no breakage.

**Design B (Callbacks)**
- Each callback is a standalone function, not a subtype — LSP is less directly applicable.
- However, if callbacks are defined as implementations of a shared interface or base class, inconsistent return types (e.g., some return `None`, some return an `LlmResponse` that short-circuits) would violate LSP.
- ⚠️ Risk of inconsistency across 18 implementations if not disciplined.

**Winner: A** (more naturally enforces the contract through the class hierarchy)

---

### I — Interface Segregation Principle
> *Clients should not be forced to depend on interfaces they don't use.*

**Design A (Plugin)**
- `HotelPolicyPlugin` only implements `before_model_callback` — the one hook it needs.
- Agents don't depend on the plugin interface at all; they don't even know it exists.
- ✅ No unnecessary dependencies forced on agents.

**Design B (Callbacks)**
- If you define a shared base class or protocol for policy callbacks, every agent is forced to depend on it — even agents where the callback does nothing meaningful.
- If callbacks are plain functions with no shared protocol, there's no interface at all — no contract, no guarantee of consistency.
- ⚠️ Either forced dependency on a shared interface, or no interface contract at all.

**Winner: A**

---

### D — Dependency Inversion Principle
> *High-level modules should not depend on low-level modules. Both should depend on abstractions.*

**Design A (Plugin)**
```
App (high-level)
  └── depends on ──► BasePlugin (abstraction)
                          ▲
                  HotelPolicyPlugin (low-level, concrete)
```
- `App` depends on `BasePlugin`, not on `HotelPolicyPlugin` directly.
- Policy files (`.md`) are loaded at runtime — the plugin doesn't hard-code policy content.
- ✅ Classic DIP: high-level module (`App`) depends on abstraction (`BasePlugin`).

**Design B (Callbacks)**
```
booking_agent (high-level)
  └── depends on ──► booking_policy_callback (concrete function)
                          └── hard-coded path to booking_agent.md
```
- Agent definitions directly reference concrete callback functions.
- No abstraction layer between the agent and the policy mechanism.
- ❌ High-level agent module directly depends on a low-level concrete function.

**Winner: A**

---

### SOLID Scorecard (Round 1)

| Principle | Design A (Plugin) | Design B (Per-agent Callbacks) |
|---|---|---|
| **S** Single Responsibility | ✅ Agents and policy fully separated | ❌ Agents carry policy responsibility |
| **O** Open/Closed | ✅ Extend without modifying agents | ❌ Every new agent requires modification |
| **L** Liskov Substitution | ✅ Cleanly substitutable via BasePlugin | ⚠️ Risk of inconsistent contract across 18 functions |
| **I** Interface Segregation | ✅ Agents have no forced policy dependency | ⚠️ Either over-dependence or no contract |
| **D** Dependency Inversion | ✅ App → BasePlugin ← HotelPolicyPlugin | ❌ Agent → concrete callback function |

**Design A wins on all five SOLID principles.**

---

### The Honest Caveat

SOLID favours Design A architecturally, but Design B has one practical advantage that SOLID doesn't capture: **observability**. Reading `booking_agent.py` and seeing `before_agent_callback=booking_policy_callback` makes the policy dependency *explicit and traceable* at the call site. In Design A, the injection is invisible unless you know to look at the plugin. This is a valid operational concern — the fix is good inline documentation on the `App` constructor and the plugin itself, not abandoning the cleaner architecture.

---

## User

> let's go back study more in details on ADK's plugin and callback functionalities, such as what are the abstraction and implementations, what are the design purpose for both, what is the ADK's recommendation to use them.

---

## Assistant — ADK Internals Deep Dive

(The following analysis was derived by reading the live ADK source code via `inspect.getsource` on `BasePlugin`, `Agent`, `base_llm_flow`, and `base_agent`.)

---

### ADK's Two Interception Systems

**Plugin** — `google.adk.plugins.BasePlugin` (abstract class, registered on `App`)  
**Agent Callbacks** — plain functions or `list[Callable]` registered directly on `Agent(...)`

Both share the same *hook names* at the agent/model/tool level, but they are architecturally different systems with different scopes.

---

### Hook Inventory — What Each System Exposes

| Hook | Plugin (`BasePlugin`) | Agent Callback (`Agent(...)`) | Scope |
|---|:---:|:---:|---|
| `on_user_message_callback` | ✅ | ❌ | Invocation start, before any agent runs |
| `before_run_callback` | ✅ | ❌ | Runner start, global setup |
| `on_event_callback` | ✅ | ❌ | Every event the runner produces |
| `after_run_callback` | ✅ | ❌ | Runner finished, global teardown |
| `close()` | ✅ | ❌ | Runner shutdown, resource cleanup |
| `before_agent_callback` | ✅ | ✅ | Before a specific agent's logic runs |
| `after_agent_callback` | ✅ | ✅ | After a specific agent's logic completes |
| `before_model_callback` | ✅ | ✅ | Before LLM call (modify `LlmRequest`) |
| `after_model_callback` | ✅ | ✅ | After LLM response (modify `LlmResponse`) |
| `on_model_error_callback` | ✅ | ✅ | LLM call failed — recover or propagate |
| `before_tool_callback` | ✅ | ✅ | Before a tool executes (validate/modify args) |
| `after_tool_callback` | ✅ | ✅ | After a tool executes (modify result) |
| `on_tool_error_callback` | ✅ | ✅ | Tool call failed — recover or propagate |

**Plugin has 5 hooks Agent callbacks don't.** All runner-lifecycle hooks (`before_run`, `after_run`, `on_event`, `on_user_message`, `close`) are plugin-only — they have no per-agent equivalent because they operate above the agent level.

---

### Execution Order — From Source Code

From `base_llm_flow.py` and `base_agent.py` (lines 210–231, 446–465):

```
Invocation start
│
├── Plugin: on_user_message_callback
├── Plugin: before_run_callback
│
│   ┌── For each agent invoked ─────────────────────────────────────┐
│   │  Plugin: before_agent_callback        ← runs first            │
│   │  Agent:  before_agent_callback        ← runs if plugin → None │
│   │                                                                │
│   │    ┌── For each LLM call ─────────────────────────────────┐   │
│   │    │  Plugin: before_model_callback   ← runs first        │   │
│   │    │  Agent:  before_model_callback   ← runs if plugin → None│  │
│   │    │  ── LLM call ──                                       │   │
│   │    │  Plugin: after_model_callback    ← runs first        │   │
│   │    │  Agent:  after_model_callback    ← runs if plugin → None│  │
│   │    └──────────────────────────────────────────────────────┘   │
│   │                                                                │
│   │    ┌── For each tool call ────────────────────────────────┐   │
│   │    │  Plugin: before_tool_callback    ← runs first        │   │
│   │    │  Agent:  before_tool_callback    ← runs if plugin → None│  │
│   │    │  ── tool executes ──                                  │   │
│   │    │  Plugin: after_tool_callback     ← runs first        │   │
│   │    │  Agent:  after_tool_callback     ← runs if plugin → None│  │
│   │    └──────────────────────────────────────────────────────┘   │
│   │                                                                │
│   │  Plugin: after_agent_callback         ← runs first            │
│   │  Agent:  after_agent_callback         ← runs if plugin → None │
│   └────────────────────────────────────────────────────────────────┘
│
├── Plugin: on_event_callback  (every yielded event)
└── Plugin: after_run_callback
```

**Critical rule from source:** If a plugin hook returns a non-`None` value, it **short-circuits all remaining plugins AND all agent callbacks** for that hook. Agent callbacks only run if the plugin passes through with `None`.

---

### ADK's Stated Design Purpose

From `BasePlugin` docstring:
> *"Plugins are best used for adding custom behaviors like **logging, monitoring, caching**, or **modifying requests and responses** at key stages."*

From `base_agent.py` field docstrings:
> `before_agent_callback`: *"optional function to be called before the agent starts… can be used to **modify or skip agent execution**."*  
> `before_model_callback`: *"optional function to be called before the model is invoked… to **modify the LLM request** or **return a cached response**."*  
> `before_tool_callback`: *"optional function to be called before a tool is invoked… to **modify tool arguments** or **skip tool execution**."*

---

### ADK's Implied Recommendation

Reading the two systems together, ADK's design intent is clear:

| Use Plugin when… | Use Agent Callback when… |
|---|---|
| Behaviour applies to **all agents** | Behaviour applies to **one specific agent** |
| You need **invocation-level hooks** (`before_run`, `on_event`, `after_run`) | You need **agent-specific lifecycle control** |
| Cross-cutting concerns: logging, tracing, auth, policy, caching | Agent-specific concerns: state init, output validation, access control |
| You want **one registration point** on `App` | You want the logic **visible and co-located** with the agent |
| The plugin must **not short-circuit** agent callbacks unintentionally | You need to **guarantee** the callback fires regardless of plugins |

---

### What This Means for Our Design

The current `HotelPolicyPlugin` is used correctly per ADK's intent — it's a cross-cutting, application-wide concern registered on `App`. But there's a subtle risk exposed by the execution order:

**If `HotelPolicyPlugin.before_model_callback` ever returns a non-`None` value** (e.g., a cached response) it would silently swallow any agent-level `before_model_callback` that exists — including the existing `_load_precreated_itinerary` logic on `root_agent`. Since our plugin always returns `None`, this is safe today. It's worth an explicit comment in the code to preserve that contract:

```python
# Always return None — returning a value would short-circuit
# all agent-level before_model_callbacks across every agent.
return None
```

The per-agent `before_agent_callback` on `root_agent` (for `_load_precreated_itinerary`) is the right pattern too — it's specific to one agent and needs session `state` access, which is exactly what agent callbacks are for.

---

## User

> now let's reevaluate the two design approaches to apply the agent level policy to each specific agents, per the SOLID principals

---

## Assistant — Revised SOLID Evaluation (with ADK Internals Knowledge)

Now with full knowledge of ADK's internals — execution order, hook semantics, and what each system is designed for — let's re-evaluate properly.

---

### What We Now Know That Changes the Analysis

Three facts from the source code matter here:

1. **Plugin `before_model_callback` always runs before agent `before_model_callback`** — and if the plugin returns non-`None`, the agent callback is silently skipped.
2. **`before_model_callback` (both systems) is semantically for modifying `LlmRequest`** — ADK's own docstring: *"inspect, log, or modify the LlmRequest… implement caching."* It is not the lifecycle hook; that's `before_agent_callback`.
3. **Agent callbacks are scoped by design** — ADK's architecture intentionally separates *global cross-cutting concerns* (plugin) from *per-agent specific concerns* (agent callback). The separation isn't just a pattern choice — it's built into the execution model.

---

### S — Single Responsibility (Re-evaluated)

**Design A (Plugin routes agent-specific policy)**
```python
# One class doing two things:
# 1. Inject general policy for ALL agents
# 2. Route and inject specific policy per agent name
class HotelPolicyPlugin(BasePlugin):
    _AGENT_POLICY_MAP = { "booking_agent": ..., "planning_agent": ..., ... }

    async def before_model_callback(self, ...):
        llm_request.append_instructions([self._general])          # concern 1
        specific = self._agent_policies.get(agent_name)           # concern 2
        if specific:
            llm_request.append_instructions([specific])
```
The plugin now has **two reasons to change**: (1) how general policy is applied globally, (2) which specific policy maps to which agent. These are independent axes of change.

**Design B (Agent-level callbacks)**
```python
# Each callback has exactly one reason to change: its agent's specific policy
async def booking_policy_callback(callback_context, llm_request):
    llm_request.append_instructions([BOOKING_POLICY])   # one concern
```
Each callback has one responsibility. The general policy stays in the plugin untouched.

**Verdict: B is better here.** The plugin in Design A conflates global and local concerns. SRP asks us to separate them.

---

### O — Open/Closed (Re-evaluated)

**Design A**

Adding a new agent (e.g., `loyalty_agent`) requires:
- **Modifying** `_AGENT_POLICY_MAP` inside `HotelPolicyPlugin`
- **Modifying** the plugin's pre-loaded file cache

```python
# Must open and modify the plugin every time a new agent is added
_AGENT_POLICY_MAP: dict[str, str] = {
    ...
    "loyalty_agent": "loyalty_agent.md",   # ← modification required
}
```
❌ Violates OCP for agent-specific routing.

**Design B**

Adding `loyalty_agent` means:
- Add `loyalty_agent.md` to `hotel_policy/`
- Write `loyalty_policy_callback` (new code, not modification)
- Wire it: `Agent(..., before_model_callback=loyalty_policy_callback)`

The plugin and all existing agent callbacks are **untouched**.
✅ Closed to modification, open to extension.

**Verdict: B wins.** Design A's `_AGENT_POLICY_MAP` is a modification hotspot.

---

### L — Liskov Substitution (Re-evaluated)

**Design A**

`HotelPolicyPlugin` is a `BasePlugin` subclass. As long as it always returns `None`, it is substitutable. But its behaviour now **depends on runtime `agent_name`** — swap it for a `NullPolicyPlugin` in tests and agent-specific policy silently disappears. The substitution changes observable behaviour in a non-obvious way.

**Design B**

Each callback is a plain `async def` matching the `BeforeModelCallback` protocol. Substituting one (e.g., in tests) affects only that one agent. The contract is narrow and predictable.

**Verdict: B is safer.** Design A's substitutability is fragile because of hidden routing state.

---

### I — Interface Segregation (Re-evaluated)

This is where ADK's execution model makes the judgment clear.

**Design A**

`before_model_callback` in the plugin fires for **every agent** — including agents that need no specific policy. The plugin internally filters them out, but it is still invoked. Agents are forced to participate in a global dispatch they didn't ask for.

More critically: the plugin hook is **semantically global**. ADK uses it for cross-cutting concerns. We are overloading it with per-agent routing logic, blending two different interface concerns into one hook.

**Design B**

`Agent(before_model_callback=booking_policy_callback)` — only `booking_agent` depends on `booking_policy_callback`. No other agent is touched. Each agent declares exactly the interface it needs.

**Verdict: B wins clearly.** Forcing a global hook to do per-agent routing violates the spirit of ISP.

---

### D — Dependency Inversion (Re-evaluated)

**Design A**

```
HotelPolicyPlugin (concrete)
  └── reads agent_name at runtime → looks up _AGENT_POLICY_MAP (concrete dict)
      └── depends on specific file names ("booking_agent.md", ...)
```

The plugin's routing logic depends on concrete agent names and concrete filenames. If an agent is renamed, the plugin breaks silently (the key is just missing from the map).

**Design B**

```
Agent (high-level)
  └── before_model_callback: BeforeModelCallback (abstraction/protocol)
                                    ▲
              booking_policy_callback (concrete, injected at construction)
```

`Agent` depends on the `BeforeModelCallback` protocol, not on a specific implementation. You can inject a mock, a no-op, or a test stub — the agent doesn't care. This is textbook DIP.

**Verdict: B wins.** Dependency is on the protocol, not on concrete routing state.

---

### Revised SOLID Scorecard

| Principle | Design A (Plugin routes all) | Design B (Agent callbacks) |
|---|---|---|
| **S** Single Responsibility | ❌ Plugin has two concerns: global + routing | ✅ Each callback owns one agent's policy |
| **O** Open/Closed | ❌ Must modify `_AGENT_POLICY_MAP` per new agent | ✅ Add new callback; existing code untouched |
| **L** Liskov Substitution | ⚠️ Substitution changes hidden routing behaviour | ✅ Narrow contract, predictable substitution |
| **I** Interface Segregation | ❌ Global hook overloaded with per-agent routing | ✅ Each agent declares exactly what it needs |
| **D** Dependency Inversion | ❌ Plugin depends on concrete names/filenames | ✅ Agent depends on callback protocol |

**Design B wins on all five when evaluated for agent-specific policy.**

---

### The Correct Hybrid — What ADK's Architecture is Telling Us

ADK's own separation is the answer. The two systems were designed to do different things:

```
Plugin (BasePlugin)                     Agent Callback
─────────────────────────────           ──────────────────────────────
Cross-cutting, ALL agents               Specific to ONE agent
Logging, tracing, monitoring            State init, specific enforcement
Invocation lifecycle hooks              Agent lifecycle hooks
before_run / on_event / after_run       before_agent / before_tool
General policy injection                Agent-specific policy injection
```

The right design follows ADK's own architecture:

```python
# Plugin: owns ONLY the general policy (one responsibility, truly global)
class HotelPolicyPlugin(BasePlugin):
    async def before_model_callback(self, *, callback_context, llm_request):
        llm_request.append_instructions([self._general_policy])
        return None   # never short-circuit; always pass through

# Per-agent: each owns its own specific policy (closed to modification)
booking_agent = Agent(
    ...,
    before_model_callback=booking_policy_callback,   # one responsibility
)
planning_agent = Agent(
    ...,
    before_model_callback=planning_policy_callback,
)
```

This also eliminates the execution-order risk: the plugin injects general policy first, then the agent callback injects specific policy. The two layers are independent, each modifying `llm_request` in sequence, neither short-circuiting the other — which is exactly what ADK's change-propagation model supports.

---

## User

> Now please re-implement it

---

## Assistant — Re-implementation

### Plan

The hybrid design was re-implemented in six steps:

| Step | Action |
|---|---|
| ✅ 1 | Simplify `plugin.py` to general policy only (remove `_AGENT_POLICY_MAP`) |
| ✅ 2 | Create `hotel_policy/callbacks.py` with 7 per-domain callback functions |
| ✅ 3 | Wire callbacks to inspiration & planning agents |
| ✅ 4 | Wire callbacks to booking & pre_trip agents |
| ✅ 5 | Wire callbacks to in_trip, post_trip & root agents |
| ✅ 6 | Verify imports and run sanity check (`Root agent OK`) |

---

### `plugin.py` — After Simplification

```python
"""ADK plugin that injects the IHG general hotel policy into every agent's
system instruction.

Design responsibility: cross-cutting, application-wide policy only.
Agent-specific policies are injected via per-agent before_model_callbacks
defined in hotel_policy/callbacks.py and wired directly to each Agent.

Execution order (from ADK internals):
  1. This plugin's before_model_callback runs first (all agents).
  2. Each agent's own before_model_callback runs next (specific agent only).
Both modify LlmRequest in sequence; this plugin always returns None so it
never short-circuits the agent-level callbacks.
"""

class HotelPolicyPlugin(BasePlugin):
    """Appends the IHG general hotel policy to every model call across all agents.

    Single responsibility: inject general_hotel_policy.md globally.
    Agent-specific policies are the responsibility of per-agent callbacks
    in hotel_policy/callbacks.py.
    """

    def __init__(self) -> None:
        super().__init__(name="hotel_policy")
        self._general_policy: str = _GENERAL_POLICY_FILE.read_text(encoding="utf-8")

    async def before_model_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_request: LlmRequest,
    ) -> Optional[LlmResponse]:
        """Append the general hotel policy to the system instruction.

        Always returns None so the agent-level before_model_callback
        is never short-circuited.
        """
        llm_request.append_instructions([self._general_policy])
        return None
```

---

### `callbacks.py` — New File

```python
"""Per-agent before_model_callbacks that inject agent-specific hotel policies.

Design:
  - Each function has a single responsibility: inject the policy for its
    designated agent domain.
  - Functions are plain async callables matching ADK's BeforeModelCallback
    protocol — Agent depends on the protocol, not on this module directly.
  - Sub-agents in the same domain share their parent domain's callback
    (e.g. place_agent and poi_agent both use inspiration_policy_callback).
  - All functions return None so they never short-circuit the ADK flow.

Execution order (ADK):
  HotelPolicyPlugin.before_model_callback  (general policy, runs first)
      └── <this callback>                  (agent-specific policy, runs second)
"""

# Load each policy file once at import time.
_ROOT_POLICY         = _load("root_agent.md")
_INSPIRATION_POLICY  = _load("inspiration_agent.md")
_PLANNING_POLICY     = _load("planning_agent.md")
_BOOKING_POLICY      = _load("booking_agent.md")
_PRE_TRIP_POLICY     = _load("pre_trip_agent.md")
_IN_TRIP_POLICY      = _load("in_trip_agent.md")
_POST_TRIP_POLICY    = _load("post_trip_agent.md")

async def root_agent_policy_callback(callback_context, llm_request) -> Optional[LlmResponse]: ...
async def inspiration_policy_callback(callback_context, llm_request) -> Optional[LlmResponse]: ...
async def planning_policy_callback(callback_context, llm_request) -> Optional[LlmResponse]: ...
async def booking_policy_callback(callback_context, llm_request) -> Optional[LlmResponse]: ...
async def pre_trip_policy_callback(callback_context, llm_request) -> Optional[LlmResponse]: ...
async def in_trip_policy_callback(callback_context, llm_request) -> Optional[LlmResponse]: ...
async def post_trip_policy_callback(callback_context, llm_request) -> Optional[LlmResponse]: ...
```

---

### Agents Wired

| Agent file | Callback applied | Agents patched |
|---|---|---|
| `inspiration/agent.py` | `inspiration_policy_callback` | `place_agent`, `poi_agent`, `inspiration_agent` |
| `planning/agent.py` | `planning_policy_callback` | `itinerary_agent`, `hotel_room_selection_agent`, `hotel_search_agent`, `planning_agent` |
| `booking/agent.py` | `booking_policy_callback` | `create_reservation`, `payment_choice`, `process_payment`, `booking_agent` |
| `pre_trip/agent.py` | `pre_trip_policy_callback` | `what_to_pack_agent`, `pre_trip_agent` |
| `in_trip/agent.py` | `in_trip_policy_callback` | `day_of_agent`, `trip_monitor_agent`, `in_trip_agent` |
| `post_trip/agent.py` | `post_trip_policy_callback` | `post_trip_agent` |
| `agent.py` (root) | `root_agent_policy_callback` | `root_agent` |

The full import chain passes cleanly (`Root agent OK`).

---

### Final Architecture

```
IHG Travel Concierge App
│
├── HotelPolicyPlugin (registered on App)
│     └── before_model_callback → injects general_hotel_policy.md
│                                  for ALL agents (runs first)
│
└── Each Agent (wired at construction)
      └── before_model_callback → injects <domain>_agent.md
                                   for THIS agent only (runs second)

Layer 1 (general):   general_hotel_policy.md    → all 18 agents
Layer 2 (specific):  booking_agent.md           → booking domain (4 agents)
                     planning_agent.md          → planning domain (4 agents)
                     inspiration_agent.md       → inspiration domain (3 agents)
                     pre_trip_agent.md          → pre-trip domain (2 agents)
                     in_trip_agent.md           → in-trip domain (3 agents)
                     post_trip_agent.md         → post-trip domain (1 agent)
                     root_agent.md             → root agent (1 agent)
```
