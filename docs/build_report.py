"""Build the six-page pilot report plus one references page from real artifacts."""
import json
import statistics
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs';OUT.mkdir(exist_ok=True)
font=Path('C:/Windows/Fonts')
if (font/'arial.ttf').exists():
    pdfmetrics.registerFont(TTFont('Body',str(font/'arial.ttf')))
    pdfmetrics.registerFont(TTFont('BodyBold',str(font/'arialbd.ttf')))
    pdfmetrics.registerFont(TTFont('Display',str(font/'georgia.ttf')))
else:
    pdfmetrics.registerFont(pdfmetrics.Font('Body','Helvetica','WinAnsiEncoding'))
    pdfmetrics.registerFont(pdfmetrics.Font('BodyBold','Helvetica-Bold','WinAnsiEncoding'))
    pdfmetrics.registerFont(pdfmetrics.Font('Display','Times-Roman','WinAnsiEncoding'))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='BodyBold')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='Text',fontName='Body',fontSize=10,leading=14.5,spaceAfter=10,textColor=colors.HexColor('#32443e')))
styles.add(ParagraphStyle(name='SmallText',parent=styles['Text'],fontSize=8.5,leading=12,spaceAfter=6))
styles.add(ParagraphStyle(name='Hero',fontName='Display',fontSize=31,leading=36,spaceAfter=17,textColor=colors.HexColor('#173f36')))
styles.add(ParagraphStyle(name='Section',fontName='Display',fontSize=23,leading=29,spaceAfter=16,textColor=colors.HexColor('#173f36')))
styles.add(ParagraphStyle(name='Sub',fontName='BodyBold',fontSize=11,leading=15,spaceBefore=8,spaceAfter=7,textColor=colors.HexColor('#173f36')))
styles.add(ParagraphStyle(name='Label',fontName='BodyBold',fontSize=8,leading=12,spaceAfter=12,textColor=colors.HexColor('#a05231')))
story=[]
def p(text,style='Text'):return Paragraph(text,styles[style])
def add(text,style='Text'):story.append(p(text,style))
def section(k,title):add(k.upper(),'Label');add(title,'Section')
def table(rows,widths):
    rows=[[p(str(c),'SmallText') for c in row] for row in rows]
    t=Table(rows,colWidths=widths,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7eee3')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#a9b8a9')),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#dce1d8'))]))
    story.extend([t,Spacer(1,12)])
def page():story.append(PageBreak())

legacy=json.loads((ROOT/'evaluation/pilot-metrics.json').read_text(encoding='utf8'))
modern=json.loads((ROOT/'evaluation/onnx-model-replay.json').read_text(encoding='utf8'))
assert len(modern)==8,'Wait for all eight development replays before publishing the report'
def mean(stage,key):return statistics.mean(r[stage][key] for r in modern)
warnings=0
for path in (ROOT/'evaluation/results').glob('*.json'):
    r=json.loads(path.read_text(encoding='utf8'))
    warnings+=bool(r['result'].get('warnings'))

add('PAPERTRAIL / RESEARCH ENGINEERING PILOT / 25 NOV 2026','Label')
add('A paper finder that<br/>shows its evidence.','Hero')
add('Product research, working agent, and an auditable improvement beyond a ranked list. Prepared against the supplied Paper Finder Agent trial brief. This is a pilot submission, with the remaining validation gaps stated explicitly.')
img=ROOT/'work/live-home.jpg'
if img.exists():story.extend([Image(str(img),width=483,height=272),Spacer(1,8)])
add('Figure 1. Actual browser capture of the deployed application. No simulated search results are shown.','SmallText')
add('The decision','Sub')
add('Build a new application around OpenAlex keyword and semantic retrieval, a local int8 GTE ModernBERT reranker, and hosted Gemini planning and analysis. Use LangGraph to bound the workflow and PostgreSQL to preserve runs. The user reviews inclusion criteria before any content assessment.')
add('What "better than Scholar" can defensibly mean','Sub')
add('The target advantage is less work checking complex inclusion requirements: an exportable evidence ledger, explicit uncertainty, and a repair search for uncovered requirements. The evidence collected here does <b>not</b> establish overall retrieval superiority over Google Scholar. In one known-item observation, Scholar clearly performed better.')
page()

section('01 / Product research','Compare real workflows, not slogans.')
add('Two tasks were observed through live interfaces: a date-constrained GNN explanation search and a partly remembered prompt-tuning method. Asta used its default mode; Scholar was tested both with the original question and with an expert keyword query plus explicit date controls. Sanitized first-ten title lists are included in the source repository.')
table([['System / mode','Observed behavior','Implication'],['Scholar: natural language','GNN search initially surfaced a 2025 result despite dates in the prose.','Use explicit date controls for a fair comparison.'],['Scholar: expert query + 2018-2024','First ten included GNNExplainer, PGExplainer, GraphFramEx and GraphSVX.','A strong, useful baseline; not merely keyword failure.'],['Asta: default Find Papers','About 75 seconds shown for the GNN task; criteria, relevance explanations, evidence and citation counts were visible. A survey ranked second.','Criteria and explanations are already present in Asta. Contribution-type constraints can still need review.'],['Known-item prompt task','Scholar put Prefix-Tuning first; it was outside Asta\'s first ten captured headings. The first MiniLM PaperTrail build placed it seventh.','This observation favors Scholar on the named target. Related deep-prompt methods may also satisfy the broad wording.']],[105,226,152])
add('Literature and source inspection','Sub')
add('LitSearch supplies realistic ML/NLP queries with expert review [7,8]. BEIR motivates testing retrieval across domains rather than assuming a pretrained ranker transfers reliably [9]. RRF combines retrieval lists without requiring comparable raw scores [10]. These informed the implementation and ablations, not a claim that this pilot reproduces those papers\' full evaluations.')
add('AllenAI\'s published Paper Finder description and frozen open-source snapshot show a structured search pipeline with LLM decisions [4,5]. A snapshot is evidence of one released implementation, not a complete description of the current live service. Scholar documentation confirms date controls, related work, citation links, and exports [6]. Scholar Labs and Asta deep search were not evaluated.')
page()

section('02 / Implementation','A bounded agent with inspectable state.')
table([['Step','Implemented behavior'],['1. Plan and review','Gemini proposes 1-3 queries, up to 5 content criteria, explicit dates and access restrictions. The user can edit all fields. Rule-based suggestions are labelled if inference fails.'],['2. Retrieve','OpenAlex keyword + native semantic search. The first semantic query retains the original question. API authentication stays server-side. Search responses are cached for 24 hours.'],['3. Select and rank','Deduplicate DOI/title versions and retain provenance. RRF selects up to 60 candidates; protect up to 20 additional original-semantic candidates. Rerank at most 80 with int8 ModernBERT on CPU.'],['4. Explore and assess','Diligent mode explores references from the first 3 leads. Recheck year, access and retraction filters. Assess the first 15 candidates using titles and abstracts.'],['5. Repair once','If an individual criterion, or their joint satisfaction in a single paper, has no supported match, issue a targeted semantic query, rerank, and reassess once. Stop at the call budget.'],['6. Explain and retain','Criteria-first ordering, evidence matrix, actual reference edges, action trace, relevance feedback, JSON/CSV/BibTeX export, and grounded reading-list Q&A.']],[110,373])
add('Why these components','Sub')
add('OpenAlex provides scholarly records and a documented semantic endpoint backed by Qwen3-Embedding-0.6B [1-3]. Native search avoids building a brittle miniature index. The 149M-parameter GTE ModernBERT reranker is an actual learned query-document model [11]; its official int8 ONNX export fits CPU hosting. RRF chooses candidates, while uncalibrated neural logits order them. Scores are not displayed as probabilities.')
add('LangGraph makes retrieval, assessment, conditional repair, and termination explicit [13]. Gemini 3.6 Flash is primary; Gemini 2.5 Flash is a same-provider fallback when the primary is unavailable. Successful model identity and actual assessment HTTP attempts are recorded. If both fail, the system retains uncertainty rather than generating a substitute explanation [12].')
add('Bounds: 12 external OpenAlex calls, 1 repair round, 30 returned candidates, 15 assessed candidates. The app does not read full papers or claim a complete literature review.','SmallText')
page()

section('03 / Proposed improvement','Turn inclusion criteria into a coverage loop.')
add('A similarity-ranked list can look relevant while relaxing an important requirement. PaperTrail exposes a paper-by-criterion ledger and uses uncovered criteria to guide a bounded follow-up search. The improvement is this inspectable loop and its retained artifacts; criteria labels and explanations alone are not claimed as novel.')
table([['Evidence case','Initial failure or risk','Current treatment'],['GNNExplainer','Relevant title alone cannot prove real-data evaluation.','A source statement explicitly mentioning synthetic and real-world graphs supports that criterion.'],['ProtGNN','An early development run treated a wide range of datasets as proof of real datasets.','The tightened assessor marks the real-data requirement uncertain when metadata does not establish it.'],['CF-GNNExplainer','Widely used datasets does not establish non-synthetic evaluation.','Keep the real-data criterion uncertain; quote presence alone cannot justify entailment.'],['Survey contributions','A survey may be useful background yet fail a new-method inclusion requirement.','Expose explicit counter-evidence where the source supports it. Missing experimental details remain uncertain.']],[108,185,190])
add('Two independent checks','Sub')
add('The model first assesses semantic support. A deterministic validator then requires an exact quote from the supplied title or abstract for any supported or contradicted judgment. Fabricated quotes and unknown sources are rejected. This checks attribution, <b>not</b> logical entailment: the first development failure passed quote matching while drawing an unjustified inference. Source review remains necessary.')
add('Ordering and repair','Sub')
add('Papers with support for every reviewed criterion appear first, followed by incomplete evidence, then explicit counter-evidence; neural relevance breaks ties. No candidate is silently declared irrelevant for lacking an abstract. If different papers cover different requirements but no single paper covers them jointly, repair also runs. The UI preserves unresolved gaps after the one allowed repair round.')
add('Reading-list Q&A reranks returned papers for the question and supplies up to 15 abstracts to the model. Each displayed claim must cite an existing result and a matching source quote. It cannot establish facts absent from those abstracts, and it is not a substitute for full-text analysis.')
page()

section('04 / Evaluation','Measure regressions and report the limits.')
add('A fixed seed selected 8 quality-2, specificity-1 queries from the first 100 official LitSearch rows before retrieval. All are inline-ACL queries, so the sample is narrow. Known targets are matched using normalized full titles. This transfers queries to OpenAlex; it is not the official 64,183-document fixed-corpus evaluation [7,8]. Unjudged results are not labelled irrelevant.')
rows=[['Initial pipeline stage','Hit@10','Target recall@10','MRR@10']]
for key,label in [('single_semantic','Single semantic'),('rrf','Hybrid RRF'),('rerank','MiniLM mixed-score rerank'),('final','Initial full ordering')]:
    m=legacy['summary'][key];rows.append([label,f"{m['hit_at_10']:.3f}",f"{m['target_recall_at_10']:.3f}",f"{m['mrr_at_10']:.3f}"])
table(rows,[225,80,100,78])
add(f'Table 1. Eight genuine initial runs. {warnings}/8 contained hosted-analysis warnings, so these are diagnostic retrieval results, not valid evidence of full-agent content-assessment quality. Index coverage, title metadata, and version differences can produce false misses. One gold title contains a venue prefix; the strict matcher leaves it unchanged.','SmallText')
rows=[['Development replay, same queries','Hit@10','Target recall@10','MRR@10']]
for key,label in [('same60_neural','ModernBERT int8, original 60'),('protected_pool_neural','ModernBERT int8, protected pool')]:
    rows.append([label,*[f'{mean(key,k):.3f}' for k in ['hit_at_10','target_recall_at_10','mrr_at_10']]])
table(rows,[225,80,100,78])
add(f'Table 2. No new hosted calls: rerank cached real candidates. Mean CPU replay time was {statistics.mean(r["seconds"] for r in modern):.1f}s per query on this machine. The same-60 control separates model choice from candidate-pool protection. This development sample informed model selection and is not an independent held-out win.','SmallText')
add('What improved, and what is unproven','Sub')
add('The pilot exposed score-scale interference and motivated a stronger CPU model plus semantic-candidate protection. The new implementation preserves raw neural ordering and tests that RRF cannot reverse it merely because the scores have different scales. No causal benefit from coverage repair, human-judged precision advantage, overall Scholar/Asta win, or statistical significance is established by this small sample.')
page()

section('05 / Delivery and next validation','A working system under user control.')
add('<b>App:</b> https://papertrail-production-da48fd85.up.railway.app<br/><b>Public code:</b> https://github.com/CosmicAlpaca/papertrail-research-agent<br/><b>Primary workspace:</b> D:/PaperTrail')
add('A separate PaperTrail project and PostgreSQL database are hosted in Hai Nguyen\'s Railway account. The database URL is a private service reference; model and OpenAlex keys are server variables. A multistage Docker build serves React and FastAPI together. The health endpoint reports model readiness and database type without credentials.')
add('Reproduce and inspect','Sub')
add('README.md includes local setup, model identities, deployment, database ownership and recovery-key instructions. The repository retains sanitized live-comparison lists, fixed tasks, genuine initial run artifacts, development model replays, and metric code. Run pytest, build the frontend, then run the pilot against a local API. Replay requires its cached OpenAlex records; see the reproducibility note in evaluation/.')
add('Verification','Sub')
add('Automated checks cover duplicate provenance, metadata restrictions after citation expansion, fabricated-quote rejection, malformed model responses, chat-source validation, inference fallback/cooldown, workspace isolation, and the score-scale regression. Browser checks cover planning, an actual search, evidence views, and hosted reading-list Q&A. The final handoff lists any remaining service limitation.')
add('Practical limits','Sub')
add('The current queue and rate limits are process-local, so deploy one worker/replica. PostgreSQL persists completed runs; interrupted jobs are marked failed after restart and preserve their plan. Production scale needs a durable worker queue, shared rate limits, migrations and operational backups. A workspace capability must be backed up privately. The current English reranker has a 512-token inference bound; abstracts and service quotas remain limiting factors.')
add('The next convincing test','Sub')
add('Freeze a separate, broader 50-query test set before further tuning. Include known-item, topical, constrained, temporal and multilingual searches. Pool and blind results from Scholar expert search, Asta default/deep search, and PaperTrail. Use two human assessors and adjudication, with full-text verification for hard criteria. Measure precision/nDCG, known-target recall, constraint violations, abstention quality, time and cost. Ablate neural ranking, criterion ordering and repair separately; report paired uncertainty intervals and all failures.')
add('The supplied brief asks for convincing comparison and rigorous improvement evidence. The code and pilot make the proposal reviewable, but the larger independent study remains unfinished. This report does not conceal that gap.','SmallText')
page()

section('References','Primary sources and artifact provenance')
refs=[
'[1] OpenAlex. Searching works. https://help.openalex.org/api/searching/',
'[2] OpenAlex. Semantic search: model, filters and limits. https://help.openalex.org/api/semantic-search/',
'[3] OpenAlex. Authentication. https://help.openalex.org/api/authentication/',
'[4] Allen Institute for AI. Paper Finder overview. https://allenai.org/blog/paper-finder',
'[5] AllenAI. Asta Paper Finder frozen open-source snapshot. https://github.com/allenai/asta-paper-finder',
'[6] Google Scholar. Search help. https://scholar.google.com/intl/en-us/scholar/help.html',
'[7] Ajith et al. (2024). LitSearch: A Retrieval Benchmark for Scientific Literature Search. EMNLP. https://aclanthology.org/2024.emnlp-main.840/',
'[8] Official LitSearch dataset and implementation. https://huggingface.co/datasets/princeton-nlp/LitSearch ; https://github.com/princeton-nlp/LitSearch',
'[9] Thakur et al. (2021). BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models. https://arxiv.org/abs/2104.08663',
'[10] Cormack, Clarke and Buettcher (2009). Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods. SIGIR. https://cormack.uwaterloo.ca/cormack/cormacksigir09-rrf.pdf',
'[11] Alibaba-NLP. GTE reranker ModernBERT base: model card and official ONNX exports. https://huggingface.co/Alibaba-NLP/gte-reranker-modernbert-base',
'[12] Google. Gemini 3.6 Flash and OpenAI compatibility. https://aistudio.google.com/docs/models/gemini-3.6-flash ; https://aistudio.google.com/docs/openai',
'[13] LangChain. LangGraph overview. https://docs.langchain.com/oss/python/langgraph/overview',
'[14] Railway. Dockerfiles, health checks and plan limits. https://docs.railway.com/builds/dockerfiles ; https://docs.railway.com/deployments/healthchecks ; https://docs.railway.com/pricing/plans'
]
for ref in refs:add(ref,'SmallText')
add('All sources accessed 25 November 2026. The user-supplied one-page trial brief is retained privately outside the public repository. Raw signed-in browser snapshots and credentials are excluded. Initial pilot results are retained unchanged; the modern-model replay is explicitly labelled development evidence.','SmallText')

def frame(c,doc):
    w,h=doc.pagesize
    c.setFillColor(colors.HexColor('#f9faf6'));c.rect(0,0,w,h,fill=1,stroke=0)
    c.setStrokeColor(colors.HexColor('#ccd6c9'));c.line(56,40,w-56,40)
    c.setFont('Body',8);c.setFillColor(colors.HexColor('#58685d'))
    c.drawString(56,27,'PAPERTRAIL  /  RESEARCH ENGINEERING PILOT')
    c.drawRightString(w-56,27,f'{doc.page} / 7')
doc=SimpleDocTemplate(str(OUT/'PaperTrail-Research-Report.pdf'),pagesize=(595.28,841.89),rightMargin=56,leftMargin=56,topMargin=47,bottomMargin=56,title='PaperTrail: Evidence-led Paper Finding',author='PaperTrail')
doc.build(story,onFirstPage=frame,onLaterPages=frame)
print(OUT/'PaperTrail-Research-Report.pdf')
