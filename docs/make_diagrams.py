"""Generates docs/architecture.svg and docs/request-loop.svg. Run: python3 docs/make_diagrams.py"""

from pathlib import Path

# Warm paper, one accent on the focal node,
# orthogonal connectors drawn before boxes, masked mono labels, 4px grid.
PAPER, PAPER2, SURFACE = "#f4f0e8", "#ebe4d6", "#fffdf9"
INK, MUTED, SOFT = "#1e1c19", "#6f6a62", "#8c857b"
ACCENT, ACCENT_TINT, LINK = "#b5543a", "#f6e7e0", "#3f6c8c"
SANS = "Inter, 'Helvetica Neue', Arial, sans-serif"
MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"
HERE = Path(__file__).parent


def mono_w(text, size, track=0.06):
    return len(text) * size * (0.62 + track)


class Svg:
    def __init__(self, width, height, ident, title, desc):
        self.out = []
        self.ident = ident
        self.w(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
               f'role="img" aria-labelledby="{ident}-title {ident}-desc">')
        self.w(f'<title id="{ident}-title">{title}</title>')
        self.w(f'<desc id="{ident}-desc">{desc}</desc>')
        self.w("<defs>")
        for mid, color in (("arrow", MUTED), ("arrow-link", LINK), ("arrow-accent", ACCENT)):
            self.w(f'<marker id="{ident}-{mid}" viewBox="0 0 8 8" refX="8" refY="4" markerWidth="8" markerHeight="8" '
                   f'markerUnits="userSpaceOnUse" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="{color}"/></marker>')
        self.w("</defs>")
        self.w(f'<rect width="{width}" height="{height}" rx="10" fill="{PAPER}"/>')

    def w(self, s):
        self.out.append(s)

    def zone(self, x, y, wd, ht, text):
        self.w(f'<rect x="{x}" y="{y}" width="{wd}" height="{ht}" rx="8" fill="rgba(30,28,25,0.025)" '
               f'stroke="rgba(30,28,25,0.16)" stroke-width="0.8" stroke-dasharray="4,3"/>')
        self.w(f'<rect x="{x+12}" y="{y-6}" width="{mono_w(text, 7, 0.14)+8:.0f}" height="12" rx="2" fill="{PAPER}"/>')
        self.w(f'<text x="{x+16}" y="{y+3}" fill="{SOFT}" font-size="7" font-family="{MONO}" letter-spacing="0.14em">{text}</text>')

    def path(self, points, color=MUTED, dashed=False, marker="arrow"):
        d = " ".join(("M" if i == 0 else "L") + f"{x},{y}" for i, (x, y) in enumerate(points))
        dash = ' stroke-dasharray="4,3"' if dashed else ""
        sw = "1" if dashed else "1.2"
        end = f' marker-end="url(#{self.ident}-{marker})"' if marker else ""
        self.w(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{dash}{end}/>')

    def label(self, text, cx=None, x=None, y=0, color=MUTED):
        width = round(mono_w(text, 8) + 8)
        width += (4 - width % 4) % 4
        left = x if x is not None else cx - width / 2
        self.w(f'<rect x="{left:.0f}" y="{y}" width="{width}" height="12" rx="2" fill="{PAPER}"/>')
        self.w(f'<text x="{left + width/2:.0f}" y="{y+9}" fill="{color}" font-size="8" font-family="{MONO}" '
               f'letter-spacing="0.06em" text-anchor="middle">{text}</text>')

    def node(self, x, y, wd, ht, tag, name, sub, fill=SURFACE, stroke=INK):
        self.w(f'<rect x="{x}" y="{y}" width="{wd}" height="{ht}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
        tw = round(mono_w(tag, 7, 0.14) + 8)
        self.w(f'<rect x="{x+12}" y="{y+10}" width="{tw}" height="12" rx="2" fill="none" stroke="{stroke}" stroke-width="0.8"/>')
        self.w(f'<text x="{x+16}" y="{y+19}" fill="{stroke}" font-size="7" font-family="{MONO}" letter-spacing="0.14em">{tag}</text>')
        self.w(f'<text x="{x+12}" y="{y+38}" fill="{INK}" font-size="12" font-weight="600" font-family="{SANS}">{name}</text>')
        self.w(f'<text x="{x+12}" y="{y+52}" fill="{MUTED}" font-size="9" font-family="{MONO}">{sub}</text>')

    def legend(self, y, items, x0=24, x1=936):
        self.w(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="rgba(30,28,25,0.12)" stroke-width="0.8"/>')
        x = x0
        for kind, fill, stroke, text in items:
            if kind == "box":
                self.w(f'<rect x="{x}" y="{y+16}" width="16" height="10" rx="2" fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
            else:
                self.w(f'<line x1="{x}" y1="{y+21}" x2="{x+16}" y2="{y+21}" stroke="{stroke}" stroke-width="1" stroke-dasharray="4,3"/>')
            self.w(f'<text x="{x+24}" y="{y+24}" fill="{MUTED}" font-size="8" font-family="{MONO}" letter-spacing="0.08em">{text}</text>')
            x += 24 + mono_w(text, 8, 0.08) + 28

    def save(self, name):
        self.w("</svg>")
        (HERE / name).write_text("\n".join(self.out) + "\n")
        print(f"wrote docs/{name}")


def architecture():
    s = Svg(960, 488, "sia-arch", "Self-Improving AI copilot architecture",
            "The advisor uses the React app, which calls the FastAPI backend on Cloud Run. The backend passes each query to "
            "the Request Orchestrator, which loads its learned memory before each turn. It answers simple lookups with five direct "
            "workspace tools (calendar, email and CRM from Firestore, holdings from a local fixture), "
            "and delegates complex tasks to two sub-agents through ADK AgentTool: the Portfolio agent and the Briefing agent, "
            "which both use Twelve Data market data. The Briefing agent saves the full brief to DraftStore and returns a short "
            "summary. A completion checker reviews each answer and sends any gap back to the orchestrator, up to two loops, "
            "before the response returns to the app. Every request is traced to Cloud Trace. All agents run on Gemini through Vertex AI.")
    s.zone(576, 32, 208, 276, "ADK AGENTTOOL · TOOLS")

    # Arrows first, so boxes sit on top.
    s.path([(152, 164), (196, 164)])
    s.path([(196, 180), (152, 180)], dashed=True)
    s.label("ASK", cx=174, y=146)
    s.path([(336, 172), (392, 172)])
    s.label("QUERY", cx=364, y=154)
    # Fan out: orchestrator to a trunk, then to each tool or sub-agent.
    s.path([(544, 172), (560, 172)], marker=None)
    s.path([(560, 84), (560, 260)], marker=None)
    for cy in (84, 172, 260):
        s.path([(560, cy), (592, cy)])
    # External data.
    s.path([(768, 84), (816, 84)], color=LINK, marker="arrow-link")
    s.label("READ", cx=792, y=66, color=LINK)
    s.path([(768, 172), (816, 172)], color=LINK, marker="arrow-link")
    s.path([(768, 260), (816, 260)], color=LINK, marker="arrow-link")
    s.label("LIVE", cx=792, y=154, color=LINK)
    # Briefing agent keeps the full brief and returns a summary.
    s.path([(680, 292), (680, 356)], dashed=True)
    s.label("FULL BRIEF", x=688, y=318)
    # Orchestrator to checker, gap back, response to the app.
    s.path([(472, 204), (472, 352)])
    s.label("ANSWER", x=480, y=272)
    s.path([(432, 352), (432, 204)], color=ACCENT, dashed=True, marker="arrow-accent")
    s.label("GAP · ≤2 LOOPS", x=336, y=300, color=ACCENT)
    s.path([(392, 384), (264, 384), (264, 204)])
    s.label("RESPONSE", x=272, y=248)
    # Tracing.
    s.path([(220, 204), (220, 384), (152, 384)], dashed=True)
    s.label("SPANS", cx=186, y=366)

    s.node(24, 140, 128, 64, "BROWSER", "React app", "copilot · calendar", stroke=MUTED)
    s.node(196, 140, 140, 64, "FASTAPI", "Backend", "Cloud Run · /api/*")
    s.node(392, 140, 152, 64, "ORCHESTRATOR", "Request router", "C · learned memory", fill=ACCENT_TINT, stroke=ACCENT)
    s.node(592, 52, 176, 64, "TOOLS", "Direct lookups", "calendar · CRM · holdings")
    s.node(592, 140, 176, 64, "SUB-AGENT", "Portfolio agent", "A · risk · drift")
    s.node(592, 228, 176, 64, "SUB-AGENT", "Briefing agent", "B · capped summary")
    s.node(816, 52, 120, 64, "FIRESTORE", "Workspace", "clients · CRM", stroke=LINK)
    s.node(816, 140, 120, 152, "TWELVE DATA", "Market data", "quotes · news", stroke=LINK)
    s.node(592, 356, 176, 64, "SQLITE", "DraftStore", "full briefs saved", fill=PAPER2, stroke=MUTED)
    s.node(392, 352, 152, 64, "CHECKER", "Completion check", "flash lite · ≥0.5")
    s.node(24, 352, 128, 64, "CLOUD TRACE", "OpenTelemetry", "every request", stroke=LINK)
    s.node(816, 356, 120, 64, "VERTEX AI", "Gemini", "3.8 flash · lite", stroke=LINK)
    s.legend(448, (("box", ACCENT_TINT, ACCENT, "FOCAL: THE ORCHESTRATOR"), ("box", SURFACE, INK, "AGENT / SERVICE"),
                   ("box", PAPER2, MUTED, "LOCAL STORE"), ("box", SURFACE, LINK, "GOOGLE CLOUD / EXTERNAL"),
                   ("dash", None, MUTED, "RETURN / SIDE OUTPUT")))
    s.save("architecture.svg")


def request_loop():
    s = Svg(960, 396, "sia-loop", "Plan, execute and check loop",
            "An advisor request goes to the orchestrator, which plans and executes it. Simple lookups use direct tools; "
            "numeric questions go to the Portfolio agent and meeting briefs to the Briefing agent. A completion checker "
            "reviews the combined answer. If it is complete with confidence of at least 0.5, the response goes to the advisor. "
            "Otherwise the gap is fed back to the orchestrator for another try, up to two loops and 25 model calls per run.")
    s.zone(380, 32, 208, 276, "ROUTED BY TASK")

    s.path([(152, 172), (196, 172)])
    s.path([(348, 172), (372, 172)], marker=None)
    s.path([(372, 84), (372, 260)], marker=None)
    for cy in (84, 172, 260):
        s.path([(372, cy), (396, cy)])
        s.path([(572, cy), (596, cy)], marker=None)
    s.path([(596, 84), (596, 260)], marker=None)
    s.path([(596, 172), (620, 172)])
    s.path([(772, 172), (816, 172)])
    s.label("DONE", cx=794, y=154)
    s.path([(696, 204), (696, 324), (272, 324), (272, 204)], color=ACCENT, dashed=True, marker="arrow-accent")
    s.label("INCOMPLETE · GAP FED BACK · ≤2 LOOPS", cx=484, y=318, color=ACCENT)

    s.node(24, 140, 128, 64, "ADVISOR", "Request", "free text", stroke=MUTED)
    s.node(196, 140, 152, 64, "ORCHESTRATOR", "Plan + execute", "≤25 model calls", fill=ACCENT_TINT, stroke=ACCENT)
    s.node(396, 52, 176, 64, "TOOLS", "Fast lookups", "calendar · CRM · holdings")
    s.node(396, 140, 176, 64, "SUB-AGENT", "Portfolio agent", "numbers · scenarios")
    s.node(396, 228, 176, 64, "SUB-AGENT", "Briefing agent", "meeting briefs")
    s.node(620, 140, 152, 64, "CHECKER", "Completion check", "stop at conf ≥ 0.5")
    s.node(816, 140, 120, 64, "ADVISOR", "Response", "with trace", stroke=MUTED)
    s.legend(356, (("box", ACCENT_TINT, ACCENT, "FOCAL: THE ORCHESTRATOR"), ("box", SURFACE, INK, "AGENT / TOOL"),
                   ("dash", None, ACCENT, "RETRY WITH THE GAP")))
    s.save("request-loop.svg")


if __name__ == "__main__":
    architecture()
    request_loop()
