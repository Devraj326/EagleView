"""Generate EagleView hackathon submission deck."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# ── Colors ──
BG_DARK   = RGBColor(0x0F, 0x17, 0x2A)
BG_CARD   = RGBColor(0x1A, 0x23, 0x3B)
ACCENT    = RGBColor(0x29, 0xB6, 0xF6)
ACCENT2   = RGBColor(0x66, 0xBB, 0x6A)
ACCENT3   = RGBColor(0xFF, 0xA7, 0x26)
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
GRAY      = RGBColor(0xB0, 0xB0, 0xB0)
RED_SOFT  = RGBColor(0xEF, 0x53, 0x50)

def set_bg(slide, color=BG_DARK):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color

def add_text(slide, left, top, width, height, text, size=18, bold=False, color=WHITE, align=PP_ALIGN.LEFT):
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.alignment = align
    return tf

def add_para(tf, text, size=16, bold=False, color=WHITE, space_before=6):
    p = tf.add_paragraph()
    p.text = text
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.space_before = Pt(space_before)
    return p

def add_card(slide, left, top, width, height, color=BG_CARD):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape

def add_kpi_card(slide, left, top, value, label, accent=ACCENT):
    card = add_card(slide, left, top, 2.7, 1.5)
    add_text(slide, left+0.2, top+0.15, 2.3, 0.8, value, size=32, bold=True, color=accent)
    add_text(slide, left+0.2, top+0.85, 2.3, 0.5, label, size=13, color=GRAY)

# ═══════════════════════════════════════════════════════════════════
# SLIDE 1: TITLE
# ═══════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
set_bg(slide)
add_text(slide, 1, 1.8, 11, 1.2, "EagleView", size=54, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)
add_text(slide, 1, 3.0, 11, 0.8, "AI-Powered Supply Chain Intelligence Platform", size=28, color=WHITE, align=PP_ALIGN.CENTER)
add_text(slide, 2, 4.2, 9, 0.8, "Governed ontology + multi-agent analytics on Snowflake", size=18, color=GRAY, align=PP_ALIGN.CENTER)
add_text(slide, 2, 5.5, 9, 0.5, "Snowflake Hackathon 2026  |  Built entirely with CoCo", size=14, color=GRAY, align=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════════════════════
# SLIDE 2: PROBLEM BRIEF
# ═══════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(slide)
add_text(slide, 0.8, 0.4, 11, 0.7, "The Problem", size=36, bold=True, color=ACCENT)

add_card(slide, 0.8, 1.3, 5.6, 2.8)
tf = add_text(slide, 1.1, 1.5, 5.0, 0.4, "What business problem does this solve?", size=16, bold=True, color=ACCENT)
add_para(tf, "Supply chain data is scattered across ERP, logistics, supplier, and IoT systems with inconsistent definitions.", size=14, color=WHITE)
add_para(tf, 'The same question — "What is our on-time delivery rate?" — yields different answers across teams because each team queries different tables with different SQL logic.', size=14, color=GRAY)

add_card(slide, 6.9, 1.3, 5.6, 2.8)
tf = add_text(slide, 7.2, 1.5, 5.0, 0.4, "Who is the target user?", size=16, bold=True, color=ACCENT)
add_para(tf, "Planning teams — demand forecasting, inventory optimization", size=14, color=WHITE)
add_para(tf, "Procurement teams — supplier evaluation, cost analysis", size=14, color=WHITE)
add_para(tf, "Logistics teams — shipment tracking, delivery performance", size=14, color=WHITE)
add_para(tf, "Finance teams — landed cost, budget variance", size=14, color=WHITE)

add_card(slide, 0.8, 4.4, 5.6, 2.6)
tf = add_text(slide, 1.1, 4.6, 5.0, 0.4, "Current pain point", size=16, bold=True, color=RED_SOFT)
add_para(tf, "No shared metric definitions across teams", size=14, color=WHITE)
add_para(tf, "Manual SQL writing with no governance", size=14, color=WHITE)
add_para(tf, "Weeks to onboard new data sources", size=14, color=WHITE)
add_para(tf, "No single source of truth for supply chain KPIs", size=14, color=WHITE)

add_card(slide, 6.9, 4.4, 5.6, 2.6)
tf = add_text(slide, 7.2, 4.6, 5.0, 0.4, "How EagleView improves it", size=16, bold=True, color=ACCENT2)
add_para(tf, "Governed ontology with canonical metric definitions", size=14, color=WHITE)
add_para(tf, "Semantic views + verified queries = same answer every time", size=14, color=WHITE)
add_para(tf, "AI-powered ingestion: minutes, not weeks", size=14, color=WHITE)
add_para(tf, "Natural language queries grounded in shared definitions", size=14, color=WHITE)

# ═══════════════════════════════════════════════════════════════════
# SLIDE 3: ARCHITECTURE DIAGRAM
# ═══════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(slide)
add_text(slide, 0.8, 0.3, 11, 0.7, "Architecture", size=36, bold=True, color=ACCENT)

# Data Sources
add_card(slide, 0.4, 1.2, 12.5, 1.0, RGBColor(0x1B, 0x5E, 0x20))
add_text(slide, 0.6, 1.3, 12, 0.4, "DATA SOURCES", size=12, bold=True, color=ACCENT2)
add_text(slide, 0.6, 1.6, 12, 0.4, "ERP Systems    |    Logistics Platforms    |    Supplier Databases    |    IoT Devices    |    Spreadsheets (CSV / Excel / JSON)", size=13, color=WHITE)

# Ingestion Layer
add_card(slide, 0.4, 2.4, 12.5, 1.2)
add_text(slide, 0.6, 2.5, 3.5, 0.3, "INGESTION LAYER", size=12, bold=True, color=ACCENT)
add_text(slide, 0.6, 2.85, 3.8, 0.7, "File Upload → Orchestrator LLM\n(splits columns across domains)\n→ Per-Domain Classification\n→ Human Review → MERGE Upsert", size=11, color=GRAY)
add_text(slide, 4.8, 2.85, 4, 0.7, "Cortex COMPLETE (llama3.1-70b)\nMulti-domain orchestrator\nSchema evolution (isNewColumn)\nMERGE-based PK dedup", size=11, color=GRAY)
add_text(slide, 9.2, 2.85, 3.5, 0.7, "12 Domain Agents (Cortex)\nTwo-tier recursion guard\nTool-calling: MergeDomainTable\nRunDomainQuery, AskAnotherAgent", size=11, color=GRAY)

# Data Layer
add_card(slide, 0.4, 3.85, 6.0, 1.6)
add_text(slide, 0.6, 3.95, 5.5, 0.3, "SNOWFLAKE DATA LAYER", size=12, bold=True, color=ACCENT)
add_text(slide, 0.6, 4.3, 2.7, 0.9, "Base Tables (11)\nSUPPLIER · PLANT · PARTS\nPO · ORDER · DELIVERY\nCUSTOMER · PRODUCT\nINVENTORY · FINANCIAL\nINBOUND SHIPMENT", size=10, color=GRAY)
add_text(slide, 3.5, 4.3, 2.7, 0.9, "Dynamic Tables (5)\nSC_OTD_METRICS\nSC_FILL_RATE\nSC_INVENTORY_POSITION\nSC_LANDED_COST\nSC_SUPPLIER_SCORECARD", size=10, color=ACCENT2)

# Semantic View
add_card(slide, 6.9, 3.85, 6.0, 1.6, RGBColor(0x0D, 0x47, 0xA1))
add_text(slide, 7.1, 3.95, 5.5, 0.3, "SEMANTIC VIEW: SC_SUPPLY_CHAIN", size=12, bold=True, color=ACCENT)
add_text(slide, 7.1, 4.3, 5.5, 1.0, "Entities: Supplier → Part → Plant → Shipment → Order → Customer\nRelationships: 5 governed join paths\nVerified Queries: 9 canonical metric definitions\n→ OTD%, Fill Rate, DOI, Landed Cost, Supplier Scorecard\n→ Same SQL every time, regardless of who asks", size=11, color=WHITE)

# Query Layer
add_card(slide, 0.4, 5.7, 6.0, 1.4)
add_text(slide, 0.6, 5.8, 5.5, 0.3, "GOVERNED PATH (Metric Questions)", size=12, bold=True, color=ACCENT2)
add_text(slide, 0.6, 6.15, 5.5, 0.7, "Cortex Analyst → Semantic View → Verified Queries\nSame answer for Planning, Procurement, Logistics\nPersona-aware routing", size=11, color=WHITE)

add_card(slide, 6.9, 5.7, 6.0, 1.4)
add_text(slide, 7.1, 5.8, 5.5, 0.3, "EXPLORATORY PATH (Ad-hoc Questions)", size=12, bold=True, color=ACCENT3)
add_text(slide, 7.1, 6.15, 5.5, 0.7, "12 Domain Agents write their own SQL\nCross-domain via AskAnotherAgent (1-hop max)\nSQL validation + defense-in-depth", size=11, color=WHITE)

# ═══════════════════════════════════════════════════════════════════
# SLIDE 4: SUPPLY CHAIN ONTOLOGY
# ═══════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(slide)
add_text(slide, 0.8, 0.3, 11, 0.7, "Supply Chain Ontology", size=36, bold=True, color=ACCENT)

# Entity-Relationship
add_card(slide, 0.8, 1.2, 7.0, 2.5)
tf = add_text(slide, 1.1, 1.35, 6.5, 0.3, "Entity-Relationship Model", size=16, bold=True, color=ACCENT)
add_para(tf, "", size=6)
add_para(tf, "Supplier ──1:N──▶ Part ──N:M──▶ Plant (via Inventory)", size=14, bold=True, color=WHITE)
add_para(tf, "     │                    │", size=14, color=GRAY)
add_para(tf, "     │                  1:N", size=14, color=GRAY)
add_para(tf, "     ▼                    ▼", size=14, color=GRAY)
add_para(tf, "Purchase Order ──▶ Inbound Shipment ──▶ Plant", size=14, bold=True, color=WHITE)
add_para(tf, "     │", size=14, color=GRAY)
add_para(tf, "     ▼", size=14, color=GRAY)
add_para(tf, "  Order ──1:1──▶ Delivery ──▶ Customer", size=14, bold=True, color=WHITE)

# Canonical Metrics
add_card(slide, 8.3, 1.2, 4.4, 2.5)
tf = add_text(slide, 8.6, 1.35, 4.0, 0.3, "Canonical Metrics", size=16, bold=True, color=ACCENT2)
add_para(tf, "", size=6)
add_para(tf, "OTD% = delivered_on_time / total_delivered", size=13, color=WHITE)
add_para(tf, "Fill Rate = shipped_qty / requested_qty", size=13, color=WHITE)
add_para(tf, "DOI = qty_on_hand / avg_daily_usage", size=13, color=WHITE)
add_para(tf, "Landed Cost = unit_cost + freight + duty + insurance", size=13, color=WHITE)
add_para(tf, "Supplier OTIF = on_time_and_full / total_POs", size=13, color=WHITE)
add_para(tf, "", size=6)
add_para(tf, "Each metric is locked in a verified query —", size=12, color=GRAY)
add_para(tf, "same SQL, every time, every persona.", size=12, color=ACCENT)

# KPI Cards
add_text(slide, 0.8, 4.0, 11, 0.5, "Live KPIs from Dynamic Tables", size=18, bold=True, color=WHITE)
add_kpi_card(slide, 0.8, 4.6, "78.87%", "On-Time Delivery", ACCENT)
add_kpi_card(slide, 3.8, 4.6, "92.10%", "Fill Rate", ACCENT2)
add_kpi_card(slide, 6.8, 4.6, "3.3 days", "Avg Days of Inventory", ACCENT3)
add_kpi_card(slide, 9.8, 4.6, "₹2,837", "Avg Landed Cost/Unit", RED_SOFT)

# Persona Consistency
add_card(slide, 0.8, 6.3, 11.8, 0.9)
tf = add_text(slide, 1.1, 6.4, 11.2, 0.3, "Persona Consistency Proof", size=16, bold=True, color=ACCENT)
add_para(tf, 'Same question — "What is overall OTD%?" — asked by Planning, Procurement, and Logistics → identical result (78.87%) every time.', size=14, color=WHITE)

# ═══════════════════════════════════════════════════════════════════
# SLIDE 5: COCO USAGE
# ═══════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(slide)
add_text(slide, 0.8, 0.3, 11, 0.7, "CoCo Usage Across Full Lifecycle", size=36, bold=True, color=ACCENT)

phases = [
    ("Planning", ACCENT, [
        "Codebase architecture analysis",
        "Gap identification vs hackathon requirements",
        "Implementation plan design",
        "Entity-relationship model design",
    ]),
    ("Development", ACCENT2, [
        "Synthetic data generation (81K+ rows)",
        "Semantic view YAML authoring",
        "Dynamic table SQL creation",
        "Domain agent setup (24 agents)",
        "Query pipeline Cortex Analyst integration",
        "Streamlit SC Command Center page",
        "Frontend persona selector",
    ]),
    ("Execution", ACCENT3, [
        "SQL execution against Snowflake",
        "Data loading (PUT + COPY INTO)",
        "Agent creation via DATA_AGENT_RUN",
        "Semantic view deployment (sv-deploy)",
        "Git commit and push to GitHub",
    ]),
    ("Testing", RED_SOFT, [
        "Canonical metric verification",
        "Agent response testing",
        "Persona consistency proof",
        "Dynamic table refresh validation",
    ]),
]

for i, (phase, color, items) in enumerate(phases):
    left = 0.5 + i * 3.15
    add_card(slide, left, 1.2, 3.0, 5.5)
    add_text(slide, left + 0.15, 1.35, 2.7, 0.4, phase, size=20, bold=True, color=color)
    for j, item in enumerate(items):
        add_text(slide, left + 0.15, 1.85 + j * 0.42, 2.7, 0.4, f"• {item}", size=11, color=WHITE)

# Skills
add_text(slide, 0.8, 6.9, 12, 0.5, "Reusable CoCo Skills:  eagleview (243 lines, full architecture)  •  sc-metrics (113 lines, canonical metric definitions — shareable across teams)", size=13, color=GRAY)

# ═══════════════════════════════════════════════════════════════════
# SLIDE 6: IMPACT STATEMENT
# ═══════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(slide)
add_text(slide, 0.8, 0.3, 11, 0.7, "Impact Statement", size=36, bold=True, color=ACCENT)

# Measurable outcomes
add_card(slide, 0.8, 1.2, 3.8, 3.0)
tf = add_text(slide, 1.1, 1.35, 3.4, 0.3, "Measurable Outcomes", size=18, bold=True, color=ACCENT)
add_para(tf, "", size=6)
add_para(tf, "Data onboarding: weeks → minutes", size=14, bold=True, color=ACCENT2)
add_para(tf, "AI orchestrator auto-classifies and routes data to the right domain tables", size=11, color=GRAY)
add_para(tf, "", size=6)
add_para(tf, "Metric consistency: 0% → 100%", size=14, bold=True, color=ACCENT2)
add_para(tf, "Verified queries guarantee identical results across all personas", size=11, color=GRAY)
add_para(tf, "", size=6)
add_para(tf, "Query time: hours → seconds", size=14, bold=True, color=ACCENT2)
add_para(tf, "Natural language questions answered by governed semantic views", size=11, color=GRAY)

# Scalability
add_card(slide, 5.0, 1.2, 3.8, 3.0)
tf = add_text(slide, 5.3, 1.35, 3.4, 0.3, "Scalability", size=18, bold=True, color=ACCENT)
add_para(tf, "", size=6)
add_para(tf, "Add new domains without code changes", size=14, bold=True, color=WHITE)
add_para(tf, "Just add an entry to domain_agents.py and rerun setup — N is not fixed", size=11, color=GRAY)
add_para(tf, "", size=6)
add_para(tf, "Dynamic tables auto-refresh", size=14, bold=True, color=WHITE)
add_para(tf, "TARGET_LAG = 1 hour — metrics stay fresh as data lands", size=11, color=GRAY)
add_para(tf, "", size=6)
add_para(tf, "Multi-surface access", size=14, bold=True, color=WHITE)
add_para(tf, "React, Streamlit, MCP — same backend, same governed answers", size=11, color=GRAY)

# Beyond demo
add_card(slide, 9.2, 1.2, 3.8, 3.0)
tf = add_text(slide, 9.5, 1.35, 3.4, 0.3, "Beyond the Demo", size=18, bold=True, color=ACCENT)
add_para(tf, "", size=6)
add_para(tf, "Any industry ontology", size=14, bold=True, color=WHITE)
add_para(tf, "Healthcare, financial services, retail — same pattern: define entities, encode as semantic views", size=11, color=GRAY)
add_para(tf, "", size=6)
add_para(tf, "Enterprise-grade RBAC", size=14, bold=True, color=WHITE)
add_para(tf, "Per-user schema isolation via Snowflake native RBAC + EXECUTE AS CALLER", size=11, color=GRAY)
add_para(tf, "", size=6)
add_para(tf, "Reusable CoCo skills", size=14, bold=True, color=WHITE)
add_para(tf, "sc-metrics skill is shareable — any team can use canonical SC metric definitions", size=11, color=GRAY)

# Innovation highlights
add_card(slide, 0.8, 4.5, 11.8, 2.5)
tf = add_text(slide, 1.1, 4.65, 11.2, 0.3, "Key Innovation: Dual-Path Architecture", size=20, bold=True, color=ACCENT)
add_para(tf, "", size=6)
add_para(tf, "Governed Path: Canonical metric questions → Cortex Analyst → Semantic View → Verified Query → deterministic SQL", size=14, color=ACCENT2)
add_para(tf, "Exploratory Path: Ad-hoc questions → Domain Agents → freestyle SQL → AskAnotherAgent for cross-domain → SQL validation", size=14, color=ACCENT3)
add_para(tf, "", size=6)
add_para(tf, "No other solution offers both governed consistency AND flexible exploration in one platform.", size=15, bold=True, color=WHITE)
add_para(tf, "Runtime relationship discovery for unknown data + semantic view governance for canonical metrics.", size=13, color=GRAY)

# ═══════════════════════════════════════════════════════════════════
# SLIDE 7: TECH STACK SUMMARY
# ═══════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(slide)
add_text(slide, 0.8, 0.3, 11, 0.7, "Technology Stack", size=36, bold=True, color=ACCENT)

rows = [
    ("LLM", "Snowflake Cortex COMPLETE (llama3.1-70b)"),
    ("Agents", "24 Cortex Agents (12 primary + 12 sub) via DATA_AGENT_RUN()"),
    ("Governed Analytics", "Cortex Analyst + Semantic View with 9 Verified Queries"),
    ("Derived Metrics", "5 Dynamic Tables (TARGET_LAG = 1 hour)"),
    ("Data Loading", "MERGE-based upserts with PK deduplication"),
    ("Backend", "FastAPI (Python) on Render — routers import sf_lib"),
    ("Frontend", "React + TypeScript + Recharts on Vercel"),
    ("Streamlit", "Streamlit-in-Snowflake (3 pages: Onboard, Dashboard, SC Command Center)"),
    ("MCP", "MCP server with 2 tools (upload_data, ask_question)"),
    ("CoCo Skills", "2 reusable skills: eagleview (architecture) + sc-metrics (metric definitions)"),
    ("RBAC", "Per-user schema isolation, EXECUTE AS CALLER, SQL validation"),
    ("Data", "11 base tables, 81K+ rows, referentially consistent synthetic SC data"),
]
for i, (label, desc) in enumerate(rows):
    y = 1.1 + i * 0.48
    add_card(slide, 0.8, y, 11.8, 0.42)
    add_text(slide, 1.0, y + 0.02, 2.8, 0.38, label, size=13, bold=True, color=ACCENT)
    add_text(slide, 3.8, y + 0.02, 8.5, 0.38, desc, size=13, color=WHITE)

# ═══════════════════════════════════════════════════════════════════
# SLIDE 8: DEMO FLOW
# ═══════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(slide)
add_text(slide, 0.8, 0.3, 11, 0.7, "Demo Flow", size=36, bold=True, color=ACCENT)

steps = [
    ("1", "Upload", "Drop a supply chain CSV\nOrchestrator routes to domains", ACCENT),
    ("2", "Review", "Tabbed schema per domain\nHuman confirms mappings", ACCENT),
    ("3", "Load", "Agents CREATE/ALTER tables\nMERGE upsert loads data", ACCENT2),
    ("4", "KPIs", "Dynamic tables compute\nOTD, Fill Rate, DOI, Landed Cost", ACCENT2),
    ("5", "Query", "Natural language question\nCortex Analyst or Domain Agents", ACCENT3),
    ("6", "Prove", "Same metric, 3 personas\nIdentical results side-by-side", ACCENT3),
]
for i, (num, title, desc, color) in enumerate(steps):
    left = 0.4 + i * 2.1
    add_card(slide, left, 1.2, 2.0, 3.5)
    # Number circle
    circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(left + 0.65), Inches(1.4), Inches(0.7), Inches(0.7))
    circle.fill.solid()
    circle.fill.fore_color.rgb = color
    circle.line.fill.background()
    tf_c = circle.text_frame
    tf_c.paragraphs[0].text = num
    tf_c.paragraphs[0].font.size = Pt(24)
    tf_c.paragraphs[0].font.bold = True
    tf_c.paragraphs[0].font.color.rgb = WHITE
    tf_c.paragraphs[0].alignment = PP_ALIGN.CENTER
    tf_c.word_wrap = False
    add_text(slide, left + 0.15, 2.3, 1.7, 0.4, title, size=16, bold=True, color=color, align=PP_ALIGN.CENTER)
    add_text(slide, left + 0.15, 2.8, 1.7, 1.5, desc, size=11, color=GRAY, align=PP_ALIGN.CENTER)

# Access info
add_card(slide, 0.8, 5.2, 11.8, 1.8)
tf = add_text(slide, 1.1, 5.35, 11.2, 0.3, "Access the Platform", size=20, bold=True, color=ACCENT)
add_para(tf, "", size=6)
add_para(tf, "Frontend (React):  https://eagle-view-ten.vercel.app/", size=15, color=WHITE)
add_para(tf, "Backend (FastAPI):  Deployed on Render (auto-deploys from GitHub)", size=15, color=WHITE)
add_para(tf, "Streamlit:  EGLE_VIEW.PUBLIC.DATAMIND (Snowflake-in-Snowflake)", size=15, color=WHITE)
add_para(tf, "GitHub:  https://github.com/Devraj326/EagleView (branch: docs/update-readme)", size=15, color=WHITE)

# ═══════════════════════════════════════════════════════════════════
# SLIDE 9: CLOSING
# ═══════════════════════════════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(slide)
add_text(slide, 1, 2.0, 11, 1.0, "EagleView", size=48, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)
add_text(slide, 1.5, 3.2, 10, 1.2,
    "Runtime flexibility for unknown data\n+ Governed consistency for canonical metrics\n= One trustworthy answer for every team",
    size=24, color=WHITE, align=PP_ALIGN.CENTER)
add_text(slide, 2, 5.0, 9, 0.5, "Built entirely with Snowflake CoCo  •  Cortex Agents  •  Cortex Analyst  •  Semantic Views", size=14, color=GRAY, align=PP_ALIGN.CENTER)
add_text(slide, 2, 6.0, 9, 0.5, "Thank You", size=28, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)

# ── Save ──
out_path = r"C:\Users\anujs\Downloads\Demo Data\SF_hackathon\EagleView\EagleView_Submission_Deck.pptx"
prs.save(out_path)
print(f"Saved: {out_path}")
