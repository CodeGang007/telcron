"""
Generate docs/database/telcron-erd.drawio (multi-page) and the table catalogue section of
docs/database/schema-design.md from schema_spec.py.

    python3 docs/database/tools/build_erd.py
"""
import html
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import schema_spec as S  # noqa: E402

KEY_W, NAME_W, TYPE_W = 34, 186, 214
TABLE_W = KEY_W + NAME_W + TYPE_W
HEAD_H, ROW_H = 30, 20
COL_GAP, ROW_GAP = 150, 46
ORIGIN_X, ORIGIN_Y = 40, 110

# Page layouts: list of columns, each a list of table names. "~name" = external reference stub.
PAGES = [
    ("2 · Identity & Access", [
        ["users"],
        ["user_identities", "sessions", "verification_tokens"],
        ["auth_events", "identity_verifications", "trust_score_events"],
    ]),
    ("3 · Catalogue & Media", [
        ["categories", "manufacturers", "brands"],
        ["products", "product_variants"],
        ["product_aliases", "product_media", "~data_sources"],
        ["media_assets", "identification_requests", "~users"],
        ["media_blobs", "embedding_models"],
        ["media_annotations", "media_embeddings", "product_embeddings"],
    ]),
    ("4 · Sources, Evidence, Recalls & Certifications", [
        ["data_sources", "ingestion_jobs", "~products"],
        ["source_records", "evidence_items", "product_traceability", "evidence_embeddings"],
        ["recalls", "recall_regions", "~embedding_models"],
        ["recall_products", "recall_product_identifiers", "recall_embeddings"],
        ["product_certifications", "certification_checks", "certification_schemes"],
    ]),
    ("5 · Screening, Hazard & Passport", [
        ["~products", "~recalls", "~evidence_items"],
        ["screenings", "screening_matches", "passport_evidence"],
        ["passports", "hazard_score_citations"],
        ["hazard_assessments", "hazard_dimension_scores"],
        ["scoring_contexts", "scoring_bands", "hazard_dimensions"],
    ]),
    ("6 · Wallet, Pricing & Risk Alerts", [
        ["~products", "~passports", "~identification_requests"],
        ["wallet_items", "wallet_labels", "wallet_item_labels"],
        ["wallet_item_verifications", "qr_labels", "product_watches", "price_alerts", "~media_assets"],
        ["user_risk_alerts", "price_snapshots", "~recalls"],
        ["risk_events", "risk_event_media", "notifications", "notification_preferences", "user_devices"],
    ]),
    ("7 · Rewards (TelCoins)", [
        ["~users", "coin_balances", "user_daily_logins", "referrals"],
        ["coin_ledger_entries", "fraud_holds", "user_badges"],
        ["coin_earn_rules", "redemptions", "reward_levels", "badges"],
        ["redemption_items", "user_entitlements"],
    ]),
    ("8 · Community & Reviews", [
        ["~products", "~media_assets", "~recalls"],
        ["reviews", "review_media", "review_votes"],
        ["posts", "post_media", "reactions"],
        ["comments", "hazard_flags", "hazard_flag_media"],
        ["product_fact_reports", "~risk_events", "~hazard_dimensions"],
        ["~users", "chat_threads", "chat_messages"],
    ]),
    ("9 · Commerce Feed & Personalisation", [
        ["~products", "~categories", "~recalls", "~posts"],
        ["feed_items", "search_queries"],
        ["feed_item_topics", "topics", "feed_interactions"],
    ]),
    ("10 · Platform, Audit & Operations", [
        ["app_settings", "audit_log", "outbox_events"],
        ["review_tasks", "feature_flags"],
        ["ai_invocations"],
    ]),
]

# Overview: domain grid positions (col, row) and curated conceptual relationships.
OVERVIEW_GRID = {
    "certs": (0, 0), "sources": (1, 0), "recalls": (2, 0), "platform": (3, 0),
    "media": (0, 1), "catalogue": (1, 1), "verification": (2, 1), "alerts": (3, 1),
    "feed": (0, 2), "community": (1, 2), "wallet": (2, 2), "pricing": (3, 2),
    "identity": (0, 3), "rewards": (1, 3),
}
OVERVIEW_EDGES = [
    ("recalls", "sources", "raw records"),
    ("certs", "sources", "authority"),
    ("certs", "catalogue", "certifies"),
    ("media", "catalogue", "identifies · illustrates"),
    ("verification", "catalogue", "screens"),
    ("verification", "recalls", "matches"),
    ("verification", "sources", "cites evidence"),
    ("alerts", "verification", "status change"),
    ("alerts", "pricing", "price drop"),
    ("wallet", "catalogue", "holds"),
    ("wallet", "verification", "re-screen"),
    ("pricing", "wallet", "target price"),
    ("community", "catalogue", "about"),
    ("community", "wallet", "from wallet"),
    ("feed", "catalogue", "cards"),
    ("feed", "community", "posts"),
    ("rewards", "community", "earn events"),
    ("rewards", "identity", "per user"),
]


def esc(s):
    return html.escape(str(s), quote=True)


def cid(*parts):
    return re.sub(r"[^A-Za-z0-9_]", "_", "_".join(parts))


def pk_cols(t):
    return set(S.pk_cols(t))


def key_label(t, c):
    keys = []
    if c.name in pk_cols(t):
        keys.append("PK")
    if c.fk:
        keys.append("FK")
    if c.uk and "PK" not in keys:
        keys.append("UK")
    return " ".join(keys)


def type_label(c):
    nullable = not (c.nn or c.pk)
    s = c.type + ("?" if nullable else "")
    if c.fk:
        pt, pc = c.fk.split(".")
        s += f" → {pt}" + ("" if pc == "id" else f".{pc}")
    return s


def table_height(t, stub_cols=None):
    n = len(stub_cols) if stub_cols is not None else len(t.cols)
    return HEAD_H + n * ROW_H


def table_tooltip(t):
    lines = [t.purpose]
    if t.features:
        lines.append(f"Features: {t.features}")
    if t.uniques:
        lines.append("Unique: " + "; ".join(map(str, t.uniques)))
    if t.checks:
        lines.append("Checks: " + "; ".join(t.checks))
    if t.indexes:
        lines.append("Indexes: " + "; ".join(map(str, t.indexes)))
    if t.fks:
        lines.append("Composite FKs: " + "; ".join(f"({f.cols}) → {f.ref}" for f in t.fks))
    if t.rules:
        lines.append("Rules: " + " ".join(t.rules))
    if t.append_only:
        lines.append("Append-only" + (f" (may change: {', '.join(t.immutable)})" if t.immutable else "") + ".")
    return "\n".join(lines)


def table_xml(t, x, y, page, stub=False, stub_cols=None):
    fill, stroke = S.DOMAINS[t.domain][1], S.DOMAINS[t.domain][2]
    tid = cid(page, "t", t.name)
    cols = [c for c in t.cols if c.name in stub_cols] if stub else t.cols
    h = table_height(t, [c.name for c in cols] if stub else None)
    if stub:
        title = f"{t.name}  (→ {S.DOMAINS[t.domain][0]})"
        style = (f"shape=table;startSize={HEAD_H};container=1;collapsible=0;childLayout=tableLayout;"
                 f"fixedRows=1;rowLines=0;fontStyle=2;align=center;resizeLast=1;html=1;dashed=1;"
                 f"fillColor=#f5f5f5;strokeColor=#999999;fontColor=#666666;fontSize=11;")
    else:
        flag = "★ " if t.core else ""
        sub = " <font style='font-size:9px' color='#555555'>append-only</font>" if t.append_only else ""
        title = f"{flag}<b>{esc(t.name)}</b>{sub}"
        sw = 3 if t.core else 1
        style = (f"shape=table;startSize={HEAD_H};container=1;collapsible=1;childLayout=tableLayout;"
                 f"fixedRows=1;rowLines=0;fontStyle=0;align=center;resizeLast=1;html=1;"
                 f"fillColor={fill};strokeColor={stroke};strokeWidth={sw};fontSize=12;")
    out = [f'<UserObject label="{esc(title) if not stub else esc(title)}" tooltip="{esc(table_tooltip(t))}" id="{tid}">'
           f'<mxCell style="{style}" vertex="1" parent="1">'
           f'<mxGeometry x="{x}" y="{y}" width="{TABLE_W}" height="{h}" as="geometry"/></mxCell></UserObject>']
    row_ids = {}
    for i, c in enumerate(cols):
        rid = cid(page, "r", t.name, c.name)
        row_ids[c.name] = rid
        rfill = "#ffffff" if not stub else "#fafafa"
        out.append(
            f'<mxCell id="{rid}" value="" style="shape=tableRow;horizontal=0;startSize=0;swimlaneHead=0;'
            f'swimlaneBody=0;fillColor={rfill};collapsible=0;dropTarget=0;points=[[0,0.5],[1,0.5]];'
            f'portConstraint=eastwest;top=0;left=0;right=0;bottom=0;strokeColor=none;" vertex="1" parent="{tid}">'
            f'<mxGeometry y="{HEAD_H + i * ROW_H}" width="{TABLE_W}" height="{ROW_H}" as="geometry"/></mxCell>')
        k = key_label(t, c)
        bold = "fontStyle=1;" if (k.startswith("PK") or c.name in pk_cols(t)) else ""
        name_style = "fontStyle=5;" if "PK" in k else ("fontStyle=0;" if c.nn or c.pk else "fontStyle=2;")
        fc = "fontColor=#888888;" if stub else ""
        cells = [(k, KEY_W, f"align=center;{bold}fontColor={'#b85450' if 'PK' in k else '#555555'};fontSize=9;"),
                 (c.name, NAME_W, f"align=left;spacingLeft=6;{name_style}{fc}fontSize=11;"),
                 (type_label(c), TYPE_W, f"align=left;spacingLeft=4;fontColor=#555555;fontSize=10;")]
        xo = 0
        for j, (val, w, st) in enumerate(cells):
            out.append(
                f'<mxCell id="{rid}_c{j}" value="{esc(val)}" style="shape=partialRectangle;connectable=0;'
                f'fillColor=none;top=0;left=0;bottom=0;right=0;overflow=hidden;whiteSpace=wrap;html=1;{st}" '
                f'vertex="1" parent="{rid}"><mxGeometry x="{xo}" width="{w}" height="{ROW_H}" as="geometry">'
                f'<mxRectangle width="{w}" height="{ROW_H}" as="alternateBounds"/></mxGeometry></mxCell>')
            xo += w
    return out, row_ids, h


def legend_xml(page, x, y):
    lid = cid(page, "legend")
    txt = ("<b>Legend</b><br/>"
           "★ thick border = <b>core</b> table (first migration set)<br/>"
           "<b>PK</b> primary key · <b>FK</b> foreign key · <b>UK</b> unique<br/>"
           "<i>italic name</i> / <b>type?</b> = nullable column<br/>"
           "<b>→ table</b> = FK target (lines drawn only between neighbouring columns)<br/>"
           "dashed grey table = defined on another page<br/>"
           "Crow's foot: ┼ one (mandatory) · o┼ zero-or-one · o&lt; zero-or-many<br/>"
           "Hover a table header for purpose, constraints &amp; indexes")
    return [f'<mxCell id="{lid}" value="{esc(txt)}" style="rounded=1;whiteSpace=wrap;html=1;align=left;'
            f'verticalAlign=top;spacing=10;fillColor=#ffffff;strokeColor=#999999;fontSize=11;arcSize=4;" '
            f'vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="390" height="150" as="geometry"/></mxCell>']


def title_xml(page, text, sub):
    return [f'<mxCell id="{cid(page, "title")}" value="{esc(f"<b>{text}</b><br/><font style='font-size:12px' color='#666666'>{sub}</font>")}" '
            f'style="text;html=1;align=left;verticalAlign=top;fontSize=20;whiteSpace=wrap;" vertex="1" parent="1">'
            f'<mxGeometry x="{ORIGIN_X}" y="20" width="1200" height="60" as="geometry"/></mxCell>']


def edge_style(nullable, unique):
    parent_end = "ERzeroToOne" if nullable else "ERmandOne"
    child_end = "ERzeroToOne" if unique else "ERzeroToMany"
    return (f"edgeStyle=entityRelationEdgeStyle;fontSize=11;html=1;endArrow={parent_end};"
            f"startArrow={child_end};endFill=0;startFill=0;rounded=0;strokeColor=#7a7a7a;")


def build_domain_page(page_name, columns):
    page = cid(page_name.split("·")[0].strip())
    on_page = {n.lstrip("~") for col in columns for n in col}
    stub_names = {n[1:] for col in columns for n in col if n.startswith("~")}
    # Which columns of each stub are actually referenced from this page
    stub_cols = {n: set() for n in stub_names}
    for child, col, parent, pcol, _ in S.fk_edges():
        if parent in stub_names and child in on_page and child not in stub_names:
            stub_cols[parent].add(pcol)
    for n in stub_names:
        if not stub_cols[n]:
            stub_cols[n] = pk_cols(S.TABLE_BY_NAME[n]) or {"id"}

    cells, rows, col_of = [], {}, {}
    x = ORIGIN_X
    max_y = 0
    for ci, col in enumerate(columns):
        y = ORIGIN_Y
        for name in col:
            stub = name.startswith("~")
            t = S.TABLE_BY_NAME[name.lstrip("~")]
            xml, rids, h = table_xml(t, x, y, page, stub=stub, stub_cols=stub_cols.get(t.name))
            cells += xml
            rows[t.name] = rids
            col_of[t.name] = ci
            y += h + ROW_GAP
        max_y = max(max_y, y)
        x += TABLE_W + COL_GAP

    edges = []
    for i, (child, col, parent, pcol, nullable) in enumerate(S.fk_edges()):
        if child == parent:
            continue  # self-references are shown by the '→ table' type label
        if child not in rows or parent not in rows or child in stub_names:
            continue
        if abs(col_of[child] - col_of[parent]) > 1:
            continue  # long-range FK: shown by the '→ table' label to keep the page readable
        src, tgt = rows[child].get(col), rows[parent].get(pcol)
        if not src or not tgt:
            continue
        ccol = next(c for c in S.TABLE_BY_NAME[child].cols if c.name == col)
        unique = ccol.uk or (pk_cols(S.TABLE_BY_NAME[child]) == {col})
        edges.append(f'<mxCell id="{cid(page, "e", str(i))}" style="{edge_style(nullable, unique)}" edge="1" '
                     f'parent="1" source="{src}" target="{tgt}"><mxGeometry relative="1" as="geometry"/></mxCell>')

    domains = sorted({S.TABLE_BY_NAME[n.lstrip('~')].domain for col in columns for n in col if not n.startswith('~')},
                     key=list(S.DOMAINS).index)
    n_tables = sum(1 for col in columns for n in col if not n.startswith("~"))
    title = title_xml(page, f"Telcron Database — {page_name.split('·', 1)[1].strip()}",
                      f"{n_tables} tables · domains: {', '.join(S.DOMAINS[d][0] for d in domains)} · PostgreSQL 18")
    legend = legend_xml(page, x, ORIGIN_Y)
    return title + cells + edges + legend


def build_overview():
    page = "overview"
    cells = title_xml(page, "Telcron Database — Domain Overview",
                      f"{len(S.TABLES)} tables in {len(S.DOMAINS)} domains · "
                      f"{sum(t.core for t in S.TABLES)} core (★) tables created first · PostgreSQL 18 "
                      f"(pgvector, pg_trgm, PostGIS, citext) · generated from schema_spec.py")
    BOX_W, CELL_W, CELL_H = 300, 380, 0
    by_dom = {d: [t for t in S.TABLES if t.domain == d] for d in S.DOMAINS}
    row_heights = {}
    for d, (c, r) in OVERVIEW_GRID.items():
        row_heights[r] = max(row_heights.get(r, 0), 34 + 18 * len(by_dom[d]) + 10)
    row_y, acc = {}, ORIGIN_Y
    for r in sorted(row_heights):
        row_y[r] = acc
        acc += row_heights[r] + 70
    ids = {}
    for d, (c, r) in OVERVIEW_GRID.items():
        name, fill, stroke = S.DOMAINS[d]
        did = cid(page, "d", d)
        ids[d] = did
        items = "<br/>".join(("★ <b>" + esc(t.name) + "</b>") if t.core else esc(t.name) for t in by_dom[d])
        label = esc(f"<b style='font-size:13px'>{esc(name)}</b><hr/>{items}")
        h = 34 + 18 * len(by_dom[d]) + 10
        cells.append(
            f'<mxCell id="{did}" value="{label}" style="rounded=1;whiteSpace=wrap;html=1;align=left;verticalAlign=top;'
            f'spacing=10;arcSize=4;fillColor={fill};strokeColor={stroke};strokeWidth=2;fontSize=11;" vertex="1" '
            f'parent="1"><mxGeometry x="{ORIGIN_X + c * CELL_W}" y="{row_y[r]}" width="{BOX_W}" height="{h}" as="geometry"/></mxCell>')
    for i, (a, b, label) in enumerate(OVERVIEW_EDGES):
        cells.append(
            f'<mxCell id="{cid(page, "oe", str(i))}" value="{esc(label)}" style="endArrow=block;endFill=1;html=1;'
            f'rounded=0;strokeColor=#555555;fontSize=10;labelBackgroundColor=#ffffff;" edge="1" parent="1" '
            f'source="{ids[a]}" target="{ids[b]}"><mxGeometry relative="1" as="geometry"/></mxCell>')
    note = ("<b>How to read</b><br/>Arrows point from the referencing domain to the referenced one "
            "(curated — the detail pages show every FK).<br/>Every user-owned domain references "
            "<b>Identity &amp; Access</b> (users); every product-related domain references the "
            "<b>Product Catalogue</b> (products).<br/><b>Reference data</b>: Sources, Recalls, Certifications "
            "· <b>User data</b>: Wallet, Community, Rewards, Feed history · <b>Derived</b>: Screening, Hazard, "
            "Passport, Risk events (reproducible from reference + user data).<br/>Pages 2–10 hold full column "
            "detail; hover a table header for constraints and indexes.")
    cells.append(f'<mxCell id="{cid(page, "note")}" value="{esc(note)}" style="rounded=1;whiteSpace=wrap;html=1;'
                 f'align=left;verticalAlign=top;spacing=10;fillColor=#ffffff;strokeColor=#999999;fontSize=11;arcSize=4;" '
                 f'vertex="1" parent="1"><mxGeometry x="{ORIGIN_X + 2 * CELL_W}" y="{row_y[3]}" width="{BOX_W * 2 + 80}" '
                 f'height="170" as="geometry"/></mxCell>')
    return cells


def diagram(name, cells, w=4000, h=3000):
    did = cid("pg", name)
    body = "".join(cells)
    return (f'<diagram name="{esc(name)}" id="{did}"><mxGraphModel dx="1600" dy="1000" grid="1" gridSize="10" '
            f'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1" pageWidth="{w}" '
            f'pageHeight="{h}" math="0" shadow="0" adaptiveColors="auto"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
            f'{body}</root></mxGraphModel></diagram>')


def build_drawio():
    pages = [diagram("1 · Overview", build_overview())]
    placed = set()
    for name, cols in PAGES:
        pages.append(diagram(name, build_domain_page(name, cols)))
        placed |= {n for col in cols for n in col if not n.startswith("~")}
    missing = [t.name for t in S.TABLES if t.name not in placed]
    if missing:
        raise SystemExit(f"Tables not placed on any page: {missing}")
    return '<mxfile host="Electron" agent="Telcron schema build_erd.py">' + "".join(pages) + "</mxfile>"


# ───────────────────────── Markdown catalogue ─────────────────────────
def build_catalogue_md():
    out = []
    for d, (dname, _, _) in S.DOMAINS.items():
        ts = [t for t in S.TABLES if t.domain == d]
        out.append(f"\n### {dname}\n")
        for t in ts:
            tags = []
            if t.core:
                tags.append("★ core")
            if t.append_only:
                tags.append("append-only")
            tags.append(f"phase {t.phase}")
            out.append(f"#### `{t.name}`" + (f" — {' · '.join(tags)}" if tags else ""))
            out.append(f"\n{t.purpose}" + (f"  \n*Serves:* {t.features}" if t.features else "") + "\n")
            out.append("| Column | Type | Null | Key | Default | Notes |\n|---|---|---|---|---|---|")
            for c in t.cols:
                k = key_label(t, c)
                typ = c.type + (f" → `{c.fk}` ({c.on_delete})" if c.fk else "")
                out.append(f"| `{c.name}` | {typ} | {'' if (c.nn or c.pk) else 'yes'} | {k} | "
                           f"{('`' + c.default + '`') if c.default else ''} | {c.note} |")
            extra = []
            if t.pk:
                extra.append(f"**Primary key:** `({', '.join(t.pk)})`")
            if t.partition_by:
                extra.append(f"**Partitioned:** monthly by `{t.partition_by}` (PK includes it)")
            if t.uniques:
                extra.append("**Unique:** " + "; ".join(f"`{u}`" for u in t.uniques))
            if t.fks:
                extra.append("**Composite FKs:** " + "; ".join(f"`({f.cols}) → {f.ref}`" + (" deferrable" if f.deferrable else "") for f in t.fks))
            if t.immutable is not None:
                extra.append("**Append-only:** " + (f"only `{', '.join(t.immutable)}` may change" if t.immutable else "insert-only"))
            if t.rules:
                extra.append("**Rules (triggers/functions):** " + " ".join(t.rules))
            if t.checks:
                extra.append("**Checks:** " + "; ".join(f"`{c}`" for c in t.checks))
            if t.indexes:
                extra.append("**Indexes:** " + "; ".join(f"`{i}`" for i in t.indexes))
            if extra:
                out.append("\n" + "  \n".join(extra))
            out.append("")
    out.append("\n### Enumerated types\n")
    out.append("| Enum | Values |\n|---|---|")
    for k, v in S.ENUMS.items():
        out.append(f"| `{k}` | {', '.join(v)} |")
    return "\n".join(out) + "\n"


def write_catalogue(md_path):
    start, end = "<!-- CATALOGUE:START -->", "<!-- CATALOGUE:END -->"
    text = md_path.read_text()
    if start not in text:
        raise SystemExit(f"{md_path} lacks catalogue markers")
    pre, rest = text.split(start, 1)
    _, post = rest.split(end, 1)
    md_path.write_text(pre + start + "\n" + build_catalogue_md() + end + post)


if __name__ == "__main__":
    errs = S.validate()
    if errs:
        raise SystemExit("\n".join(errs))
    (ROOT / "telcron-erd.drawio").write_text(build_drawio())
    md = ROOT / "schema-design.md"
    if md.exists():
        write_catalogue(md)
    print(f"Wrote {ROOT / 'telcron-erd.drawio'}" + (" and catalogue in schema-design.md" if md.exists() else ""))
