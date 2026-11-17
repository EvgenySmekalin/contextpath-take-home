# Part 2: building and shipping the real version with a team

Thousands of Windows desktops at ten clients, software that sees everything employees type and
look at, and a popup that has to appear at the moment of the action.

## Questions before code

- Who writes rules, us or each client's admins, and how often do they change?
- Which is worse, a wrong popup or a missed one? It decides how strict matching is.
- What may leave the employee's machine? A legal question per client and country.
- Can the recorder give us the accessibility element under the cursor instead of OCR?

## The system

**Rules run on the employee's machine; only popups leave it.** Keystrokes, clipboard and screen
text stay on the device, the popup needs no network, and the numbers stay small. The take-home
data has about 5 popups per employee-hour: 5,000 employees make roughly 200,000 popups a day,
under 10 a second. Raw events are about 10 MB per employee-hour, some 400 GB a day. So:

- **No Kafka.** One Postgres behind a stateless ingest API is enough. A broker earns its place
  only if raw events go to the cloud or the popup stream gets several consumers.
- **A load balancer, yes**: for availability and deploys without downtime, not for load.
- **The queue that matters is on the device**: a small outbox on disk, uploaded in batches, so
  laptops that are offline and server outages lose nothing. Ingest is idempotent.
- **HTTPS, not UDP.** A popup is an audit record and must not be lost, and client networks let
  little else out.
- **A control plane for rules**: versioned per tenant, validated, rolled out in stages.
- **Multi-tenant from the first commit**: tenant id on every row, device identity per agent.

The take-home leaves out the outbox, resumable event streams, tolerance for broken events,
state age limits, metrics and authentication. All of them belong in the agent and ingest above.

## The team

Contracts first, so people can work in parallel: the event schema, the rule schema with its
semantics as executable examples, and the agent-to-server API. Then four streams with owners:

| Stream | Owns |
|---|---|
| Desktop agent | Rule engine, popup UI, installer, auto-update, CPU and memory budget |
| Rules platform | Authoring, validation, replay testing, staged rollout |
| Backend | Ingest, storage, audit API, tenants and devices |
| Release and operations | CI/CD, signing, fleet telemetry, on-call |

**Recordings are the test suite.** A corpus of consented, redacted recordings with reviewed
expected popups; every engine or rule change is replayed in CI and the diff in popups is shown
in the pull request. Rule authors replay a draft rule against their own tenant before enabling it.

## Shipping

1. Our own machines.
2. Shadow mode at one pilot client: rules are evaluated and reported, nothing is shown.
3. Visible popups for a small group, with a "not useful" button.
4. Client by client, each starting in shadow mode.

Agent versions go out in rings (1%, 10%, 50%, 100%) and halt automatically on crashes or
resource use. Rule sets roll back independently, with a kill switch per tenant and per rule. We
watch popup latency, agent CPU and memory, and the dismissal rate per rule.

## Risks to raise early

- **OCR as the source of clicked text** is fragile; push for accessibility data.
- **Trust**: what is collected, what leaves the device and for how long is a deliverable.
- **Endpoint security products** flag software that hooks input; signing and allow-listing with
  each client's IT takes calendar time and starts on day one.
