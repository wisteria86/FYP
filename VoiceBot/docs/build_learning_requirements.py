"""Render the proposed learning requirements agreed in the project discussion."""
from pathlib import Path
from html import escape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output'/'pdf'/'Hikari_Learning_and_Business_Negotiation_Requirements.pdf'
OUT.parent.mkdir(parents=True,exist_ok=True)
INK=colors.HexColor('#24334b'); RED=colors.HexColor('#800d2e'); GRAY=colors.HexColor('#596579')
styles={
 'title':ParagraphStyle('title',fontName='Helvetica-Bold',fontSize=23,leading=28,textColor=RED,spaceAfter=12),
 'intro':ParagraphStyle('intro',fontName='Helvetica',fontSize=10,leading=14,textColor=GRAY,spaceAfter=12),
 'heading':ParagraphStyle('heading',fontName='Helvetica-Bold',fontSize=11,leading=14,textColor=RED,spaceAfter=4),
 'body':ParagraphStyle('body',fontName='Helvetica',fontSize=10,leading=13.5,textColor=INK,spaceAfter=4),
 'accept':ParagraphStyle('accept',fontName='Helvetica',fontSize=9.5,leading=13,textColor=GRAY,spaceAfter=11),
 'source':ParagraphStyle('source',fontName='Helvetica',fontSize=9,leading=13,textColor=GRAY,spaceAfter=12),
}
LING=[
 ('L1','Observable learning outcomes',
  'Every lesson must define what the learner must do, the language involved, and acceptable evidence. Example: arrange an appointment by proposing a time, responding to availability, and confirming the agreement.',
  'Store objectives, prerequisites, an assessment rubric, and examples of acceptable alternative answers.'),
 ('L2','Assess communication, not keyword appearance',
  'Accept correct paraphrases. Mentioning a phrase, copying an example, or promising to perform a skill does not demonstrate the skill.',
  'Test paraphrases, negations, irrelevant keyword-rich answers, and incomplete task outcomes.'),
 ('L3','Separate task achievement from language quality',
  'Score task completion, comprehension and relevance, grammar and vocabulary, and interaction separately. Pronunciation requires a valid audio-based assessment.',
  'Understandable but imperfect English may complete a task without receiving a perfect language score.'),
 ('L4','Use a teach-practise-transfer cycle',
  'Offer a model when needed, guide practice, gradually remove support, and introduce a related unfamiliar situation.',
  'Repeating a supplied example alone cannot establish independent competence.'),
 ('L5','Selective, actionable corrections',
  'Prioritize errors that block meaning or relate to the current objective. Avoid correcting every sentence or demanding endless repetition.',
  'Quote the actual learner wording, offer a meaning-preserving improvement, and provide an opportunity to use it.'),
 ('L6','Teach listening and conversational repair',
  'Practise asking for repetition, checking understanding, clarifying ambiguity, and correcting misunderstandings.',
  'Treat clarification requests as useful communication, not failure or making excuses.'),
 ('L7','Appropriate language for relationships and settings',
  'Neighbours, interviewers, and dissatisfied customers must behave differently. Teach politeness, register, turn-taking, and cultural alternatives without declaring one cultural style universally correct.',
  'Define each scenario\'s roles, relationships, shared facts, and coherent conversational purpose.'),
 ('L8','Native-language support without compulsory translation',
  'Provide adjustable beginner captions and explanations. Gradually remove assistance where appropriate; do not force translation into every exchange.',
  'Distinguish supported from independent performance. Validate each supported language separately.'),
 ('L9','Do not confuse recognition errors with learner errors',
  'Speech-recognition uncertainty must not automatically reduce grammar or proficiency scores.',
  'Allow transcript disputes and corrections, record the correction, and exclude unreliable audio evidence from assessment.'),
 ('L10','Prioritize intelligibility over accent imitation',
  'Do not classify regional or non-native accents as errors merely because they differ from a preferred voice.',
  'Never judge pronunciation from text alone. Validate audio-based pronunciation features across relevant accents.'),
 ('L11','Revisit skills and measure transfer',
  'Schedule retrieval practice and later tasks with different details, speakers, or settings. Measure learning beyond time spent using the app.',
  'Distinguish completed today, retained later, and transferred to another scenario.'),
 ('L12','Use proficiency labels honestly',
  'Thirty lessons can form a useful curriculum; completing them does not automatically establish a CEFR proficiency level.',
  'Tie proficiency claims to validated assessment evidence, not lesson counts or uncalibrated LLM scores.'),
]
PSYCH=[
 ('P1','Make mistakes safe',
  'AI characters may challenge a proposal without humiliating the learner. Clearly frame difficult interactions as simulations.',
  'Prohibit ridicule, insults, personal labels, and punitive feedback.'),
 ('P2','Give learners meaningful control',
  'Allow choice of goals, scenarios, challenge level, correction style, captions, and manual versus automatic speaking.',
  'Allow pause, skip, or exit without losing earned progress or pressure to continue.'),
 ('P3','Increase challenge gradually',
  'Progress from supported one-to-one practice toward demanding or multi-AI interactions.',
  'Adapt challenge using demonstrated performance and learner preference, not only time or a rigid lesson number.'),
 ('P4','Manage cognitive load',
  'Listening, response planning, captions, and remembering corrections compete for attention.',
  'Introduce manageable targets, present one clear prompt at a time, and keep optional diagnostics outside the main learner call interface.'),
 ('P5','Specific, credible encouragement',
  'Replace automatic praise with observations, such as: you checked the customer\'s concern before proposing a solution.',
  'Ground praise in evidence; do not hide mistakes or inflate scores.'),
 ('P6','Build confidence through demonstrated improvement',
  'Show what the learner can now do, using examples from their own practice.',
  'Explain improved behaviours instead of relying only on percentages, badges, or streaks.'),
 ('P7','Support reflection and accurate self-assessment',
  'Invite learners to predict or reflect on performance, then compare their view with evidence.',
  'Keep reflection brief and useful; for example, ask what they would change in their next response.'),
 ('P8','Avoid endless failure loops',
  'A missing objective must trigger improved scaffolding, not repetition of the same question indefinitely.',
  'After repeated difficulty, offer a hint, worked example, easier subtask, pause, or exit. Not yet demonstrated must not mean incapable.'),
 ('P9','Separate completion from lasting mastery',
  'A successful exchange warrants closure. Durable competence needs further evidence.',
  'End a successful session without claiming permanent mastery; allow later review to revise skill estimates.'),
 ('P10','Keep simulated social interaction transparent',
  'Use believable characters without pretending they are real humans.',
  'Explain that participants are AI, establish roleplay boundaries, and let learners control confrontational scenario intensity.'),
 ('P11','Protect dignity, accessibility, and privacy',
  'Quiet speech, disability, fatigue, unfamiliar accents, or camera refusal must not imply low intelligence, poor motivation, or psychological weakness.',
  'Keep camera use optional. Explain recording and retention choices. Do not turn posture indicators into personality or confidence diagnoses.'),
 ('P12','Evaluate learning, not engagement alone',
  'Enjoyment, daily use, and session completion do not establish that learning occurred.',
  'Evaluate independent performance, delayed retention, transfer, perceived usefulness, and feedback utility. Compare with qualified human raters where feasible.'),
]
NEGOTIATION=[
 ('N1','Prepare alternatives, targets, and walk-away limits',
  'Teach a best alternative to a negotiated agreement (BATNA), an aspiration target, a reservation point, and an estimated zone of possible agreement (ZOPA). Keep assumptions distinct from known facts.',
  'Require a private preparation brief with justified limits and alternatives. Do not force learners to reveal their reservation point to the counterpart.'),
 ('N2','Discover interests before proposing solutions',
  'Teach learners to distinguish stated positions from underlying needs, ask diagnostic questions, listen, and confirm priorities before bargaining.',
  'Credit questions and accurate summaries that reveal a tradeable interest. Do not award discovery credit for merely saying what do you want.'),
 ('N3','Use coherent, bounded business scenarios',
  'Define price or budget, scope, timing, quality, risk, and authority where relevant. Give each party consistent public facts and private constraints; vary cases without changing facts mid-session.',
  'Check numerical consistency and feasibility. AI participants must not invent budgets, policies, market facts, or new limits solely to prolong the exercise.'),
 ('N4','Make evidence-based offers and counteroffers',
  'Teach opening offers, responses to anchors, and counteroffers grounded in supplied benchmarks, costs, service levels, or precedents. Neither always opening first nor always splitting the difference is a universal rule.',
  'Require a rationale for an offer. Label invented simulation benchmarks as fictional; unsupported real-world market claims receive no evidence credit.'),
 ('N5','Create value across multiple issues',
  'Include opportunities to exchange lower-priority terms for higher-priority benefits, rather than treating negotiation as a price-only contest.',
  'Support at least one multi-issue scenario with different party priorities. Evaluate package trade-offs, feasibility, and joint value where the case provides a utility rubric.'),
 ('N6','Make deliberate, conditional concessions',
  'Practise conditional exchanges, reciprocity, and keeping track of concessions. Distinguish a proposed concession from an accepted commitment.',
  'Record the term changed, requested return, and acceptance status. Repeated one-sided concessions or breaches of stated limits must not automatically earn a success score.'),
 ('N7','Maintain realistic counterpart behaviour',
  'AI negotiators must react to actual offers, follow their assigned interests, remember commitments, and adapt resistance to the lesson level. They should neither concede instantly nor obstruct every reasonable proposal.',
  'Test acceptance, justified rejection, clarification, and impasse paths. Repeating a scripted demand regardless of the learner\'s proposal fails the scenario.'),
 ('N8','Require ethical and professional negotiation',
  'Teach respectful firmness, truthful use of supplied facts, confidentiality, and recognition of coercive or discriminatory conduct. Strategic privacy is different from fabricating evidence or authority.',
  'Do not reward threats, harassment, fabricated offers, or unauthorized disclosure. Provide a safe exit and a debrief when a lesson includes difficult tactics.'),
 ('N9','Represent stakeholders, teams, and authority',
  'In multi-AI lessons, give participants distinct decision rights, interests, and speaking turns. Support allies, opponents, approval dependencies, and team coordination.',
  'An AI without approval authority cannot finalize a binding simulated deal. Assess how the learner identifies decision makers and handles escalation without inventing authorization.'),
 ('N10','Close with clear, executable terms',
  'Teach learners to summarize agreed price, scope, responsibilities, deadlines, and any approvals or contingencies relevant to the case. A vague yes is not a complete business agreement.',
  'Check mutual confirmation, consistent units and amounts, feasibility, ownership, and next steps. Store agreed, tentative, and unresolved terms separately.'),
 ('N11','Allow justified no-deal outcomes',
  'A negotiated agreement is not always better than the available alternative. A respectful walk-away or justified escalation can demonstrate the lesson objectives when agreement would violate constraints.',
  'Include a no-ZOPA case. Permit successful learning completion for a justified no-deal decision; incomplete learning triggers support, not endless pressure to accept a harmful deal.'),
 ('N12','Assess decision quality separately from eloquence',
  'Separate preparation, discovery, value creation, concession discipline, ethics, and implementation quality from language fluency. Evaluate results relative to the case, not merely the size of a discount.',
  'Use a scenario-specific rubric with quoted learner evidence and a validated offer ledger. Debrief missed trades, compare with alternatives, and test transfer in a fresh case.'),
]
story=[]
def p(text,style='body'):return Paragraph(text,styles[style])
def section(title,intro,items):
 story.extend([p(title,'title'),p(intro,'intro')])
 for code,title,requirement,acceptance in items:
  story.append(KeepTogether([p(f'{code}  |  {escape(title)}','heading'),p(escape(requirement)),p('<b>Acceptance:</b> '+escape(acceptance),'accept')]))
section('Language learning requirements',
 'HIKARI / REQUIREMENTS 01-06<br/>Purpose: build independent communicative ability, not merely chatbot usage. Proposed requirements; implementation and validation are not implied. Linguistic foundation: communicative, action-oriented learning [1].',LING[:6])
story.append(PageBreak())
section('Language learning requirements',
 'HIKARI / REQUIREMENTS 07-12<br/>Apply these rules across language lessons and the linguistic aspects of workplace roleplay. Spaced retrieval and transfer should extend practice beyond one successful session [2].',LING[6:])
story.append(PageBreak())
section('Educational-psychology requirements',
 'HIKARI / REQUIREMENTS 01-06<br/>Support autonomy, competence, and respectful connection [3]. These are educational design rules, not clinical assessment, diagnosis, or treatment.',PSYCH[:6])
story.append(PageBreak())
section('Educational-psychology requirements',
 'HIKARI / REQUIREMENTS 07-12<br/>Protect learner agency and dignity. Progress should represent supported learning evidence, not unsupported claims about personality, emotion, or mental health.',PSYCH[6:])
story.append(PageBreak())
section('Business negotiation requirements',
 'HIKARI / REQUIREMENTS N1-N6<br/>A business-training perspective: develop sound decisions and sustainable agreements, not agreement at any cost. Preparation and offer strategy are grounded in negotiation guidance [4, 5]. These are simulation requirements, not legal or financial advice.',NEGOTIATION[:6])
story.append(PageBreak())
section('Business negotiation requirements',
 'HIKARI / REQUIREMENTS N7-N12<br/>Preserve realistic business constraints, ethical conduct, and stakeholder authority. A successful learning outcome can be a well-justified no-deal decision; it does not require every scenario to end in agreement [5].',NEGOTIATION[6:])
story.append(PageBreak())
story.extend([p('Implementation priorities','title'),p('HIKARI / DELIVERY AND EVIDENCE','intro')])
priorities=[
 ('1. Validated lesson-specific rubrics','Separate communicative task achievement from language quality. Tie every decision to observable learner evidence.','L1-L3, L12'),
 ('2. Consistent completion decisions','Use a shared decision for dialogue closure, the progress display, and the final assessment.','L2-L3, P8-P9'),
 ('3. A support ladder','Respond to difficulty with better scaffolding and useful alternatives rather than repetitive questioning.','L4-L6, P3-P4, P8'),
 ('4. Recognition-error safeguards','Ensure microphone or recognition failures do not become learning failures.','L9-L10, P11'),
 ('5. Transfer and delayed review','Establish whether learners can retain and independently use a skill beyond the original session.','L11-L12, P7, P9, P12'),
 ('6. Negotiation state and valid business outcomes','Track offers, concessions, authority, and commitments. Evaluate feasible agreements and justified no-deal outcomes separately from language quality.','N1-N12, L3, P9'),
]
for title,body,refs in priorities:
 story.append(KeepTogether([p(title,'heading'),p(body),p('Related requirements: '+refs,'accept')]))
story.extend([Spacer(1,9),p('Source references','heading'),p('The requirements are proposed product-design applications of the guidance below. The sources do not certify Hikari, validate its scoring, or establish an ideal numerical threshold for every learner.','intro')])
sources=[
 ('[1] Council of Europe - CEFR mediation and action-oriented learning','https://www.coe.int/en/web/common-european-framework-reference-languages/mediation'),
 ('[2] Institute of Education Sciences - Organizing Instruction and Study to Improve Student Learning','https://ies.ed.gov/ncee/wwc/PracticeGuide/1'),
 ('[3] Deci, Vallerand, Pelletier and Ryan (1991) - Motivation and Education: The Self-Determination Perspective','https://selfdeterminationtheory.org/SDT/documents/1991_DeciVallerandPelletierRyan_EP.pdf'),
 ('[4] Harvard Program on Negotiation - When to Make the First Offer in Negotiations','https://www.pon.harvard.edu/daily/dealmaking-daily/resolving-the-first-offer-dilemma-in-business-negotiations/'),
 ('[5] James K. Sebenius - BATNAs in Negotiation: Common Errors and Three Kinds of No','https://www.hbs.edu/ris/download.aspx?name=17-055.pdf'),
]
for title,url in sources:
 story.append(p(f'<b>{escape(title)}</b><br/><link href="{url}" color="#315c96">{escape(url)}</link>','source'))
def page(canvas,doc):
 w,h=A4
 canvas.setStrokeColor(colors.HexColor('#e6d9d5'));canvas.line(42,h-34,w-42,h-34)
 canvas.setFont('Helvetica-Bold',8);canvas.setFillColor(RED);canvas.drawString(42,h-24,'HIKARI  /  LEARNING DESIGN REQUIREMENTS')
 canvas.setFont('Helvetica',8);canvas.setFillColor(GRAY)
 canvas.drawString(42,23,'Proposed requirements | Prepared 5 November 2026')
 canvas.drawRightString(w-42,23,f'{doc.page}')
doc=SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=49,bottomMargin=42,
 title='Hikari - Learning and Business Negotiation Requirements',author='Hikari Project',subject='36 proposed requirements across language learning, educational psychology, and business negotiation; acceptance criteria, priorities and references')
doc.build(story,onFirstPage=page,onLaterPages=page)
print(OUT)
