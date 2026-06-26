/* ============================================================
   score.seoryon.com — client-side i18n + scoring UI.

   Languages: EN (default, source) · DE · FR.
   Language priority: ?lang= URL param > localStorage > navigator.
   DE and FR are natively localized (not literal translations).
   Brand/product names (SEOryon, Oryon, ChatGPT, Perplexity, Gemini,
   Google AI, Claude, GitHub, PyPI) and technical terms kept as
   convention (schema, canonical, robots.txt, llms.txt, hreflang,
   FAQPage, JSON-LD, GEO) are left as-is across all languages.

   The scoring backend (POST to /api/score?url=...) is unchanged.
   ============================================================ */
(() => {
  "use strict";

  // ----- I18N DICTIONARY (EN source · DE · FR natively localized) -----
  const I18N = {
    en: {
      meta_title: "Free AI search readiness score · GEO audit for any URL · SEOryon",
      meta_desc: "Free GEO / AI-search readiness score for any URL — 27 signals across schema, content, authority, crawlability and freshness. Generative engine optimization audit, no signup, no LLM calls. By SEOryon.",

      nav_learn: "What is GEO?",
      nav_faq: "FAQ",
      cta_trial: "Start free trial →",

      hero_pill: "Live · 27 signals · 5 buckets · Free forever",
      hero_h1: 'Score any URL for <span class="brand-text">AI search readiness</span>.',
      hero_sub: "Twenty-seven signals across schema, content format, authority, crawlability, and freshness. A free GEO (generative engine optimization) audit, inspired by Google's 2026 AI-search guidance. Results in 10 seconds — no signup, no LLM calls, no API keys.",
      score_btn: "Score it →",
      hero_micro: "Paste an article URL, not the homepage. The deeper the page, the more useful the score.",

      b1_name: "Schema & structure", b1_meta: "8 signals · 30 pts",
      b2_name: "Content format",     b2_meta: "5 signals · 25 pts",
      b3_name: "Authority",          b3_meta: "5 signals · 20 pts",
      b4_name: "Crawlability",       b4_meta: "6 signals · 15 pts",
      b5_name: "Freshness",          b5_meta: "3 signals · 10 pts",

      dl1_title: "Star on GitHub",
      dl1_sub: "Open source · MIT · Audit your whole sitemap",
      dl2_sub: "Score URLs from your terminal · CI-friendly",

      how_h2: "How it works",
      how1_h3: "You paste a URL",
      how1_p: "Any public page. We fetch it the same way Google's AI crawlers do — same browser headers, same network path.",
      how2_h3: "We score 27 signals",
      how2_p: "Schema markup, FAQ blocks, heading structure, llms.txt, robots permissions, word count, dated claims, and more. No LLM calls.",
      how3_h3: "You get the fixes",
      how3_p: "A 0–100 score plus the top 8 fixes ranked by impact. Each fix tells you what to change, where, and why.",

      learn_kicker: "WHAT'S GEO?",
      learn_h2: "AI search is changing what “ranking” means.",
      learn_lead: "A growing share of searches now end in an AI-generated answer — Google AI Overviews, ChatGPT, Perplexity, Gemini, Claude — instead of ten blue links. Those answers quote a handful of sources. GEO (generative engine optimization) is about being one of them.",
      learn_c1_h: "Classic SEO ranks pages. GEO earns citations.",
      learn_c1_p: "Google still ranks pages in its index. But when the answer is generated, the assistant cites the sources it used. To get traffic from AI search, your page has to be <em>quotable</em> — clear, structured, well-attributed.",
      learn_c2_h: "AI engines reward extractable structure.",
      learn_c2_p: "Direct answers in the first 60 words. Question-style H2s. FAQPage schema. Definition lists. Real tables instead of images of tables. These aren't tricks — they're the shape AI summarizers can lift verbatim and credit you for.",
      learn_c3_h: "AI crawlers need permission.",
      learn_c3_p: "GPTBot, ClaudeBot, PerplexityBot, Google-Extended, and CCBot all read your robots.txt. If you block them — by accident or default — you're invisible to the answer. A simple llms.txt at your site root helps them prioritize.",
      learn_c4_h: "Freshness and authority still matter.",
      learn_c4_p: "Assistants prefer recently updated, sourced content — dated claims, a real author byline, outbound links to .gov / .edu / Wikipedia, an exposed dateModified. The fundamentals of trustworthy writing carry over, with sharper edges.",
      learn_buckets_intro: "The free score on this page checks 27 signals across five buckets:",
      learn_b1_desc: "Article / FAQ / HowTo / Breadcrumb JSON-LD, heading hierarchy, definition lists, question-style H2s.",
      learn_b2_desc: "Word count in the lift-worthy range, a direct answer in the first 60 words, a TL;DR block, bold key claims, real lists.",
      learn_b3_desc: "Named author / byline, citations to authority domains, healthy internal/outbound link density, quotes & sources.",
      learn_b4_desc: "HTTPS, canonical, mobile viewport, Open Graph, llms.txt at site root, robots.txt that lets the major AI crawlers in.",
      learn_b5_desc: "dateModified or Last-Modified header, dated phrases in the body, year in the title where it makes sense.",

      upsell_h2: 'One page is the demo. <span class="brand-text">Your whole site is the product.</span>',
      upsell_p: "This tool scores one URL at a time. Oryon scores every URL on your site continuously, tracks where you're cited across ChatGPT, Perplexity, Gemini, and Google AI — then writes the articles that get you cited.",
      upsell_cta: "Start your 3-day free trial →",
      upsell_fine: "3-day free trial · 3 published articles · 1 in-depth LLM/GEO audit · Cancel in two clicks.",
      stat1_label: "ChatGPT mentions secured for clients",
      stat2_label: "Ranking articles created",
      stat3_label: "Avg organic growth in 6 months",

      faq_h2: "Questions, answered",
      faq_gA: "AI search & GEO basics",
      faq_gB: "Using the free score",
      faq_gC: "SEOryon vs. the alternatives",
      faq_gD: "Trust & how it works",

      faq1_q: "What is GEO (generative engine optimization)?",
      faq1_a: "GEO is optimizing to be a source AI answers cite — in ChatGPT, Perplexity, Gemini, Claude, and Google's AI Overviews — instead of only ranking in the ten blue links. More and more people ask an AI assistant instead of scrolling a results page, and the assistant quotes a handful of sources. GEO is the work of being one of them: clear structure, genuinely useful answers, the right markup, and crawler access for AI bots.",
      faq2_q: "How do I get cited in ChatGPT, Perplexity, and Google AI?",
      faq2_a: "You earn citations the way you earn rankings — by being the clearest, most useful answer to a real question — but AI rewards a few extra things: well-structured content it can extract (headings, concise answers, lists, FAQ markup), demonstrated expertise and trust signals (named author, citations to authority sources), and a site that lets AI crawlers in. The free score on this page tells you exactly where you stand on the 27 signals that drive citation likelihood.",
      faq3_q: "How is ranking in AI answers different from ranking on Google?",
      faq3_a: "Google ranks pages; AI answers cite sources inside a generated reply. The fundamentals overlap — quality, structure, authority — but AI rewards content that directly answers the question in the first sentences, uses lifted-able structure (lists, definitions, Q&A), and exposes machine-readable markup. A page can rank well classically and still lose AI citations if it buries the answer. SEOryon optimizes for both.",
      faq4_q: "Why are AI Overviews changing SEO?",
      faq4_a: "Because the assistant gives the user the answer on the results page. If you're not one of the cited sources, the click never happens. That doesn't kill SEO — it shifts the prize. The new prize is being the quotable source. The work to win it is structural (clear answers, schema, llms.txt, robots access) on top of the same content quality you'd want anyway.",

      faq5_q: "What do the 5 buckets and 27 signals mean?",
      faq5_a: "The score is normalized to 100 across five buckets weighted by their influence on AI citation: schema & structure (30 pts, 8 signals), content format (25 pts, 5 signals), authority (20 pts, 5 signals), crawlability (15 pts, 6 signals), freshness (10 pts, 3 signals). Each signal returns pass / partial / fail with a specific fix telling you exactly what to change.",
      faq6_q: "Why paste an article URL, not the homepage?",
      faq6_a: "Homepages are navigation hubs; AI assistants rarely cite them. They cite specific, deep pages that answer a specific question — articles, guides, FAQs, comparison pages. Score the deepest, most useful page you have. The result will tell you a lot more about how citable your real content is.",
      faq7_q: "Is the score really free? No signup, no LLM calls?",
      faq7_a: "Yes. The scorer is a deterministic HTML parser — it fetches your URL, reads the markup, and runs 27 rule-based checks. No LLM calls, no API keys, no account, no rate-limit gating. The code is open-source under MIT, and you can self-host it or run it from your terminal with pip install oryon-score.",
      faq8_q: "What's the difference between the free score and the SEOryon platform?",
      faq8_a: "The free score audits one URL at a time, on demand. SEOryon (the paid platform) does it continuously across every URL on your site, tracks where you're actually being cited across ChatGPT, Perplexity, Gemini, Google AI, and Claude — and writes the articles that get you cited in the first place. The score answers “is this page citable?”. SEOryon answers “what should I publish next, and where am I winning?”.",

      faq9_q: "How is SEOryon different from a keyword tool or an AI writer?",
      faq9_a: "Keyword tools stop at a list — they tell you what people search, then leave the hard part (deciding what's actually worth writing, and writing it) to you. AI writers do the opposite: they generate text fast, but with no grounding in live search data, so you get generic articles that don't rank. SEOryon closes the loop. A single agent reads real search signals — live SERPs, People Also Ask, keyword difficulty, competitor gaps, trends — decides which topics will actually move your traffic and why, then writes each article on that data and checks the facts. You get the research of a keyword tool and the output of a writer, connected, instead of paying for both and stitching them together yourself.",
      faq10_q: "Do I still need Ahrefs or Semrush?",
      faq10_a: "For most teams, no. SEOryon already tracks the things those tools surface — your rankings, your competitors, your backlinks, and your site's technical health — but instead of stopping at a dashboard you have to act on, it acts: it turns those signals into published content that ranks. Ahrefs and Semrush are reference libraries; SEOryon is the team that reads the library and does the work. Keep them if you love the data, but you won't need them to grow.",
      faq11_q: "Why SEOryon instead of an agency or doing it manually?",
      faq11_a: "An agency is expensive, slow, and you're never quite sure what you're paying for; doing SEO yourself eats hours every week on research, writing, and tracking. SEOryon runs that entire research-to-publish loop continuously, for a fraction of an agency retainer — and unlike an agency, nothing is a black box: you see every recommendation and approve every article. You get agency-scale output with full control and none of the busywork.",

      faq12_q: "Is AI-written content penalized by Google?",
      faq12_a: "No — Google rewards helpful content regardless of how it's made, and penalizes spam. SEOryon writes genuine, fact-grounded articles you review before publishing, not spun filler. The score on this page is itself rule-based: it never produces or rewrites your content, it just measures whether your existing page is structured to be cited.",
      faq13_q: "Do you follow Google's rules?",
      faq13_a: "Always. No black-hat tactics, no link-exchange pools, no spun content — only the fundamentals of good SEO, because that's the only growth that lasts. The score's advice maps to the same fundamentals Google's own AI-search guidance describes.",
      faq14_q: "Does SEOryon edit my site?",
      faq14_a: "No. SEOryon shows you the data and writes the content; you publish and stay in full control of your own site. We never edit your site for you. The free score is read-only — it fetches the public URL and reads the HTML, nothing more.",
      faq15_q: "Who controls what gets published?",
      faq15_a: "You do. On semi-autopilot you approve every piece with one click; on full autopilot SEOryon publishes on your rules. Either way, nothing goes live without your say.",
      faq16_q: "What's included in the 3-day free trial?",
      faq16_a: "A 3-day free trial of the full SEOryon platform: 3 published articles written for you and 1 in-depth LLM/GEO audit, with full access. Cancel in two clicks — no card gymnastics, no auto-renewal traps.",

      footer_privacy: "Privacy",
      footer_github: "Open source on GitHub",
      footer_note: "A free GEO audit by SEOryon — your organic growth engine. Inspired by the structured-signal approach in citation-intelligence by AutomateLab. This tool is original work under MIT.",

      // result-card runtime strings
      r_scoring: "fetching · parsing · scoring",
      r_top_fixes: "Top fixes",
      r_top_fixes_sub: "(ranked by impact)",
      r_whats_working: "What's working",
      r_grade: "Grade",
      r_scoring_btn: "Scoring…",
    },

    /* ---- DE · natively localized (informal "du", marketer tone) ---- */
    de: {
      meta_title: "Kostenloser GEO- & KI-Such-Score · SEO-Audit jeder URL · SEOryon",
      meta_desc: "Kostenloser GEO- / KI-Such-Score für jede URL — 27 Signale aus Schema, Inhalt, Autorität, Crawlbarkeit und Aktualität. Generative Engine Optimization, ohne Anmeldung, ohne LLM-Aufrufe. Von SEOryon.",

      nav_learn: "Was ist GEO?",
      nav_faq: "FAQ",
      cta_trial: "Kostenlos testen →",

      hero_pill: "Live · 27 Signale · 5 Kategorien · Für immer kostenlos",
      hero_h1: 'Prüfe, wie bereit eine URL für die <span class="brand-text">KI-Suche</span> ist.',
      hero_sub: "Siebenundzwanzig Signale aus Schema, Inhaltsformat, Autorität, Crawlbarkeit und Aktualität. Ein kostenloses GEO-Audit (Generative Engine Optimization), inspiriert von Googles KI-Such-Leitlinien für 2026. Ergebnis in 10 Sekunden — ohne Anmeldung, ohne LLM-Aufrufe, ohne API-Schlüssel.",
      score_btn: "Jetzt prüfen →",
      hero_micro: "Füge eine Artikel-URL ein, nicht die Startseite. Je tiefer die Seite, desto aussagekräftiger der Score.",

      b1_name: "Schema & Struktur",   b1_meta: "8 Signale · 30 Pkt.",
      b2_name: "Inhaltsformat",       b2_meta: "5 Signale · 25 Pkt.",
      b3_name: "Autorität",           b3_meta: "5 Signale · 20 Pkt.",
      b4_name: "Crawlbarkeit",        b4_meta: "6 Signale · 15 Pkt.",
      b5_name: "Aktualität",          b5_meta: "3 Signale · 10 Pkt.",

      dl1_title: "Auf GitHub bewerten",
      dl1_sub: "Open Source · MIT · Prüfe deine ganze Sitemap",
      dl2_sub: "URLs aus dem Terminal prüfen · CI-tauglich",

      how_h2: "So funktioniert’s",
      how1_h3: "Du fügst eine URL ein",
      how1_p: "Beliebige öffentliche Seite. Wir rufen sie so ab, wie es die KI-Crawler von Google tun — gleiche Browser-Header, gleicher Netzwerkpfad.",
      how2_h3: "Wir prüfen 27 Signale",
      how2_p: "Schema-Markup, FAQ-Blöcke, Überschriftenstruktur, llms.txt, Robots-Regeln, Wortzahl, datierte Aussagen und mehr. Keine LLM-Aufrufe.",
      how3_h3: "Du bekommst die Lösungen",
      how3_p: "Ein Score von 0–100 plus die acht wirkungsvollsten Verbesserungen. Jede sagt dir, was du wo und warum ändern solltest.",

      learn_kicker: "WAS IST GEO?",
      learn_h2: "Die KI-Suche verändert, was „Ranken“ bedeutet.",
      learn_lead: "Immer mehr Suchanfragen enden in einer KI-generierten Antwort — Google AI Overviews, ChatGPT, Perplexity, Gemini, Claude — statt in zehn blauen Links. Diese Antworten zitieren eine Handvoll Quellen. Bei GEO (Generative Engine Optimization) geht es darum, eine davon zu sein.",
      learn_c1_h: "Klassisches SEO bringt Rankings. GEO bringt Zitate.",
      learn_c1_p: "Google rankt weiterhin Seiten in seinem Index. Aber wenn die Antwort generiert wird, nennt der Assistent die Quellen, die er genutzt hat. Damit du aus der KI-Suche Traffic bekommst, muss deine Seite <em>zitierfähig</em> sein — klar, strukturiert, gut belegt.",
      learn_c2_h: "KI-Engines belohnen extrahierbare Struktur.",
      learn_c2_p: "Direkte Antworten in den ersten 60 Wörtern. H2-Überschriften als Frage. FAQPage-Schema. Definitionslisten. Echte Tabellen statt Bilder von Tabellen. Das sind keine Tricks — das ist die Form, die KI-Zusammenfasser wörtlich übernehmen und dir gutschreiben können.",
      learn_c3_h: "KI-Crawler brauchen Zugang.",
      learn_c3_p: "GPTBot, ClaudeBot, PerplexityBot, Google-Extended und CCBot lesen alle deine robots.txt. Wenn du sie aussperrst — versehentlich oder per Voreinstellung —, bist du in der Antwort unsichtbar. Eine schlichte llms.txt im Stammverzeichnis hilft ihnen zusätzlich beim Priorisieren.",
      learn_c4_h: "Aktualität und Autorität zählen weiterhin.",
      learn_c4_p: "Assistenten bevorzugen aktuelle, belegte Inhalte — datierte Aussagen, eine echte Autorenangabe, ausgehende Links zu .gov / .edu / Wikipedia, ein sichtbares dateModified. Die Grundlagen vertrauenswürdigen Schreibens gelten weiter, nur mit härteren Kanten.",
      learn_buckets_intro: "Der kostenlose Score auf dieser Seite prüft 27 Signale in fünf Kategorien:",
      learn_b1_desc: "JSON-LD für Article / FAQ / HowTo / Breadcrumb, Überschriftenhierarchie, Definitionslisten, H2 als Frage.",
      learn_b2_desc: "Wortzahl im zitierfähigen Bereich, eine direkte Antwort in den ersten 60 Wörtern, ein TL;DR-Block, fett markierte Kernaussagen, echte Listen.",
      learn_b3_desc: "Namentlicher Autor / Byline, Belege zu Autoritätsdomains, gesunde interne und externe Linkdichte, Zitate & Quellen.",
      learn_b4_desc: "HTTPS, Canonical, Mobile Viewport, Open Graph, llms.txt im Stammverzeichnis, robots.txt, die die großen KI-Crawler hereinlässt.",
      learn_b5_desc: "dateModified oder Last-Modified-Header, datierte Phrasen im Fließtext, Jahreszahl im Titel, wo sinnvoll.",

      upsell_h2: 'Eine Seite ist das Demo. <span class="brand-text">Deine ganze Website ist das Produkt.</span>',
      upsell_p: "Dieses Tool prüft jeweils eine URL. Oryon prüft laufend jede URL deiner Website, verfolgt, wo du in ChatGPT, Perplexity, Gemini und Google AI zitiert wirst — und schreibt dann die Artikel, die dich dort hineinbringen.",
      upsell_cta: "3 Tage kostenlos testen →",
      upsell_fine: "3 Tage kostenlos testen · 3 veröffentlichte Artikel · 1 ausführliches LLM/GEO-Audit · In zwei Klicks kündbar.",
      stat1_label: "ChatGPT-Erwähnungen für Kunden gesichert",
      stat2_label: "Rankende Artikel erstellt",
      stat3_label: "Durchschn. organisches Wachstum in 6 Monaten",

      faq_h2: "Antworten auf häufige Fragen",
      faq_gA: "KI-Suche & GEO – die Grundlagen",
      faq_gB: "Den kostenlosen Score nutzen",
      faq_gC: "SEOryon im Vergleich",
      faq_gD: "Vertrauen & Funktionsweise",

      faq1_q: "Was ist GEO (Generative Engine Optimization)?",
      faq1_a: "GEO bedeutet, dafür zu optimieren, eine Quelle zu sein, die KI-Antworten zitieren — in ChatGPT, Perplexity, Gemini, Claude und den AI Overviews von Google — statt nur in den zehn blauen Links zu ranken. Immer mehr Menschen fragen einen KI-Assistenten, anstatt eine Ergebnisseite durchzuscrollen, und der Assistent zitiert eine Handvoll Quellen. Bei GEO geht es darum, eine davon zu sein: klare Struktur, wirklich hilfreiche Antworten, das richtige Markup und Zugang für KI-Crawler.",
      faq2_q: "Wie werde ich in ChatGPT, Perplexity und Google AI zitiert?",
      faq2_a: "Zitate verdienst du dir wie Rankings – indem du die klarste und hilfreichste Antwort auf eine echte Frage bist. Doch die KI belohnt ein paar Dinge zusätzlich: gut strukturierten Inhalt, den sie herauslösen kann (Überschriften, knappe Antworten, Listen, FAQ-Markup), nachweisbare Expertise und Vertrauenssignale (namentlicher Autor, Belege zu Autoritätsquellen) sowie eine Website, die KI-Crawler hereinlässt. Der kostenlose Score auf dieser Seite zeigt dir genau, wo du bei den 27 Signalen stehst, die über deine Zitierwahrscheinlichkeit entscheiden.",
      faq3_q: "Wie unterscheidet sich das Ranking in KI-Antworten vom Google-Ranking?",
      faq3_a: "Google rankt Seiten; KI-Antworten zitieren Quellen innerhalb einer generierten Antwort. Die Grundlagen überschneiden sich – Qualität, Struktur, Autorität –, aber die KI belohnt Inhalte, die die Frage in den ersten Sätzen direkt beantworten, eine extrahierbare Struktur nutzen (Listen, Definitionen, Q&A) und maschinenlesbares Markup bieten. Eine Seite kann klassisch gut ranken und trotzdem KI-Zitate verlieren, wenn sie die Antwort vergräbt. SEOryon optimiert für beides.",
      faq4_q: "Warum verändern AI Overviews das SEO?",
      faq4_a: "Weil der Assistent dem Nutzer die Antwort direkt auf der Ergebnisseite gibt. Bist du nicht unter den zitierten Quellen, passiert der Klick nie. Das tötet das SEO nicht – es verschiebt den Preis. Der neue Preis ist, die zitierfähige Quelle zu sein. Die Arbeit dafür ist strukturell (klare Antworten, Schema, llms.txt, Robots-Zugang) – auf derselben Inhaltsqualität, die du sowieso anstreben würdest.",

      faq5_q: "Was bedeuten die 5 Kategorien und 27 Signale?",
      faq5_a: "Der Score wird auf 100 normalisiert und auf fünf Kategorien verteilt, gewichtet nach ihrem Einfluss auf KI-Zitate: Schema & Struktur (30 Pkt., 8 Signale), Inhaltsformat (25 Pkt., 5 Signale), Autorität (20 Pkt., 5 Signale), Crawlbarkeit (15 Pkt., 6 Signale), Aktualität (10 Pkt., 3 Signale). Jedes Signal liefert bestanden / teilweise / nicht bestanden – mit einer konkreten Lösung, was du genau ändern sollst.",
      faq6_q: "Warum eine Artikel-URL einfügen und nicht die Startseite?",
      faq6_a: "Startseiten sind Navigations-Hubs; KI-Assistenten zitieren sie selten. Sie zitieren spezifische, tiefe Seiten, die eine konkrete Frage beantworten – Artikel, Guides, FAQs, Vergleichsseiten. Prüfe die tiefste, hilfreichste Seite, die du hast. Das Ergebnis sagt viel mehr darüber aus, wie zitierfähig dein eigentlicher Inhalt ist.",
      faq7_q: "Ist der Score wirklich kostenlos? Ohne Anmeldung, ohne LLM-Aufrufe?",
      faq7_a: "Ja. Der Scorer ist ein deterministischer HTML-Parser – er ruft deine URL ab, liest das Markup und führt 27 regelbasierte Prüfungen aus. Keine LLM-Aufrufe, keine API-Schlüssel, kein Konto, keine Rate-Limits. Der Code ist Open Source unter MIT, und du kannst ihn selbst hosten oder per pip install oryon-score im Terminal nutzen.",
      faq8_q: "Was unterscheidet den kostenlosen Score von der SEOryon-Plattform?",
      faq8_a: "Der kostenlose Score prüft eine URL auf Abruf. SEOryon (die kostenpflichtige Plattform) tut das laufend für jede URL deiner Website, verfolgt, wo du in ChatGPT, Perplexity, Gemini, Google AI und Claude tatsächlich zitiert wirst – und schreibt die Artikel, die dich überhaupt erst zitierfähig machen. Der Score beantwortet: „Ist diese Seite zitierfähig?“. SEOryon beantwortet: „Was sollte ich als Nächstes veröffentlichen, und wo gewinne ich gerade?“.",

      faq9_q: "Wie unterscheidet sich SEOryon von einem Keyword-Tool oder einem KI-Schreiber?",
      faq9_a: "Keyword-Tools hören bei einer Liste auf: Sie sagen dir, wonach gesucht wird, und überlassen dir den schwierigen Teil – zu entscheiden, was sich wirklich zu schreiben lohnt, und es dann auch zu schreiben. KI-Schreiber machen es umgekehrt: Sie produzieren schnell Text, aber ohne Bezug zu echten Suchdaten – heraus kommen generische Artikel, die nicht ranken. SEOryon schließt diese Lücke. Ein einziger Agent wertet echte Suchsignale aus – Live-SERPs, ähnliche Fragen, Keyword-Schwierigkeit, Wettbewerber-Lücken, Trends –, entscheidet, welche Themen deinen Traffic wirklich voranbringen und warum, schreibt dann jeden Artikel auf Basis dieser Daten und prüft die Fakten. Du bekommst die Recherche eines Keyword-Tools und die Texte eines Autors aus einer Hand – statt für beides zu zahlen und es selbst zusammenzustückeln.",
      faq10_q: "Brauche ich noch Ahrefs oder Semrush?",
      faq10_a: "Für die meisten Teams nicht. SEOryon erfasst bereits, was diese Tools anzeigen – deine Rankings, deine Wettbewerber, deine Backlinks und die technische Gesundheit deiner Website. Aber statt bei einem Dashboard haltzumachen, auf das du erst reagieren musst, handelt SEOryon: Es macht aus diesen Signalen veröffentlichte Inhalte, die ranken. Ahrefs und Semrush sind Nachschlagewerke; SEOryon ist das Team, das im Nachschlagewerk liest und die Arbeit erledigt. Behalte sie, wenn du die Daten liebst – zum Wachsen brauchst du sie nicht.",
      faq11_q: "Warum SEOryon statt einer Agentur oder manueller Arbeit?",
      faq11_a: "Eine Agentur ist teuer und langsam, und du weißt nie ganz genau, wofür du zahlst; SEO selbst zu machen, frisst Woche für Woche Stunden für Recherche, Texten und Tracking. SEOryon erledigt diesen kompletten Kreislauf von der Recherche bis zur Veröffentlichung laufend – zu einem Bruchteil eines Agenturhonorars. Und anders als bei einer Agentur gibt es keine Blackbox: Du siehst jede Empfehlung und gibst jeden Artikel frei. Du bekommst Output auf Agenturniveau, mit voller Kontrolle und ohne den lästigen Aufwand.",

      faq12_q: "Wird KI-geschriebener Inhalt von Google abgestraft?",
      faq12_a: "Nein – Google belohnt hilfreiche Inhalte, egal wie sie entstanden sind, und straft Spam ab. SEOryon schreibt echte, faktenbasierte Artikel, die du vor der Veröffentlichung prüfst – keinen zusammengesponnenen Fülltext. Der Score auf dieser Seite ist selbst regelbasiert: Er erstellt oder verändert deine Inhalte nie, er misst nur, ob deine bestehende Seite so strukturiert ist, dass sie zitiert werden kann.",
      faq13_q: "Haltet ihr euch an Googles Regeln?",
      faq13_a: "Immer. Keine Black-Hat-Tricks, keine Link-Tausch-Pools, kein gesponnener Content – nur die Grundlagen von gutem SEO, denn nur dieses Wachstum hält. Die Empfehlungen des Scores entsprechen denselben Grundlagen, die Googles eigene KI-Such-Leitlinien beschreiben.",
      faq14_q: "Bearbeitet SEOryon meine Website?",
      faq14_a: "Nein. SEOryon zeigt dir die Daten und schreibt die Inhalte; veröffentlichen tust du, und die volle Kontrolle über deine Website bleibt bei dir. Wir bearbeiten deine Website nie für dich. Der kostenlose Score ist reiner Lesezugriff – er ruft die öffentliche URL ab und liest das HTML, mehr nicht.",
      faq15_q: "Wer entscheidet, was veröffentlicht wird?",
      faq15_a: "Du. Im Semi-Autopilot gibst du jeden Beitrag per Klick frei; im Voll-Autopilot veröffentlicht SEOryon nach deinen Regeln. So oder so geht nichts ohne deine Zustimmung online.",
      faq16_q: "Was ist in der 3-tägigen kostenlosen Testphase enthalten?",
      faq16_a: "Ein 3-tägiger kostenloser Test der vollständigen SEOryon-Plattform: 3 fertig für dich geschriebene, veröffentlichte Artikel und 1 ausführliches LLM/GEO-Audit, mit vollem Zugriff. In zwei Klicks kündbar – ohne Kreditkarten-Theater, ohne automatische Verlängerungsfallen.",

      footer_privacy: "Datenschutz",
      footer_github: "Open Source auf GitHub",
      footer_note: "Ein kostenloses GEO-Audit von SEOryon – deiner Engine für organisches Wachstum. Inspiriert vom Ansatz strukturierter Signale aus citation-intelligence von AutomateLab. Dieses Tool ist eigene Arbeit unter MIT-Lizenz.",

      r_scoring: "abrufen · parsen · bewerten",
      r_top_fixes: "Wichtigste Verbesserungen",
      r_top_fixes_sub: "(nach Wirkung)",
      r_whats_working: "Was bereits funktioniert",
      r_grade: "Note",
      r_scoring_btn: "Prüfe…",
    },

    /* ---- FR · natively localized (vouvoiement, marketer tone) ---- */
    fr: {
      meta_title: "Score gratuit de visibilité dans la recherche IA · Audit GEO · SEOryon",
      meta_desc: "Score gratuit de préparation à la recherche IA / GEO pour n’importe quelle URL — 27 signaux entre schema, contenu, autorité, crawlabilité et fraîcheur. Audit de generative engine optimization, sans inscription, sans appel à un LLM. Par SEOryon.",

      nav_learn: "C’est quoi, le GEO ?",
      nav_faq: "FAQ",
      cta_trial: "Essai gratuit →",

      hero_pill: "En direct · 27 signaux · 5 catégories · Gratuit à vie",
      hero_h1: 'Évaluez la <span class="brand-text">visibilité IA</span> de n’importe quelle URL.',
      hero_sub: "Vingt-sept signaux entre schema, format du contenu, autorité, crawlabilité et fraîcheur. Un audit GEO (generative engine optimization) gratuit, inspiré des recommandations de Google pour la recherche IA en 2026. Résultats en 10 secondes — sans inscription, sans appel à un LLM, sans clé d’API.",
      score_btn: "Lancer l’analyse →",
      hero_micro: "Collez une URL d’article, pas la page d’accueil. Plus la page est profonde, plus le score est utile.",

      b1_name: "Schema & structure",  b1_meta: "8 signaux · 30 pts",
      b2_name: "Format du contenu",   b2_meta: "5 signaux · 25 pts",
      b3_name: "Autorité",            b3_meta: "5 signaux · 20 pts",
      b4_name: "Crawlabilité",        b4_meta: "6 signaux · 15 pts",
      b5_name: "Fraîcheur",           b5_meta: "3 signaux · 10 pts",

      dl1_title: "Star sur GitHub",
      dl1_sub: "Open source · MIT · Auditez tout votre sitemap",
      dl2_sub: "Analysez des URL depuis votre terminal · prêt pour la CI",

      how_h2: "Comment ça marche",
      how1_h3: "Vous collez une URL",
      how1_p: "N’importe quelle page publique. Nous l’appelons comme le font les robots IA de Google — mêmes en-têtes navigateur, même chemin réseau.",
      how2_h3: "Nous évaluons 27 signaux",
      how2_p: "Balisage schema, blocs FAQ, hiérarchie des titres, llms.txt, autorisations robots, nombre de mots, mentions datées, et plus encore. Aucun appel à un LLM.",
      how3_h3: "Vous recevez les correctifs",
      how3_p: "Un score de 0 à 100 plus les huit correctifs les plus rentables. Chacun vous dit quoi changer, où et pourquoi.",

      learn_kicker: "C’EST QUOI, LE GEO ?",
      learn_h2: "La recherche IA change le sens du mot « se positionner ».",
      learn_lead: "Une part croissante des recherches se termine désormais par une réponse générée par l’IA — Google AI Overviews, ChatGPT, Perplexity, Gemini, Claude — au lieu des dix liens bleus. Ces réponses citent une poignée de sources. Le GEO (generative engine optimization), c’est l’art d’en être une.",
      learn_c1_h: "Le SEO classique classe des pages. Le GEO gagne des citations.",
      learn_c1_p: "Google continue à classer les pages dans son index. Mais quand la réponse est générée, l’assistant cite les sources qu’il a utilisées. Pour obtenir du trafic depuis la recherche IA, votre page doit être <em>citable</em> — claire, structurée, bien attribuée.",
      learn_c2_h: "Les moteurs IA récompensent une structure extractible.",
      learn_c2_p: "Une réponse directe dans les soixante premiers mots. Des H2 sous forme de question. Le schema FAQPage. Des listes de définitions. De vrais tableaux plutôt que des images de tableaux. Ce ne sont pas des astuces : c’est la forme que les synthétiseurs IA peuvent reprendre mot pour mot, en vous créditant.",
      learn_c3_h: "Les robots IA ont besoin d’une autorisation.",
      learn_c3_p: "GPTBot, ClaudeBot, PerplexityBot, Google-Extended et CCBot lisent tous votre robots.txt. Si vous les bloquez — par accident ou par défaut — vous êtes invisible dans la réponse. Un simple llms.txt à la racine du site les aide à prioriser.",
      learn_c4_h: "La fraîcheur et l’autorité comptent toujours.",
      learn_c4_p: "Les assistants préfèrent les contenus récents et sourcés — mentions datées, vraie signature d’auteur, liens sortants vers .gov / .edu / Wikipedia, un dateModified exposé. Les fondamentaux d’une écriture fiable restent valables, avec des bords plus tranchants.",
      learn_buckets_intro: "Le score gratuit de cette page vérifie 27 signaux répartis en cinq catégories :",
      learn_b1_desc: "JSON-LD Article / FAQ / HowTo / Breadcrumb, hiérarchie des titres, listes de définitions, H2 sous forme de question.",
      learn_b2_desc: "Nombre de mots dans la plage citable, réponse directe dans les soixante premiers mots, bloc TL;DR, claims clés en gras, vraies listes.",
      learn_b3_desc: "Auteur nommé / byline, citations vers des domaines d’autorité, densité saine de liens internes et sortants, citations & sources.",
      learn_b4_desc: "HTTPS, canonique, viewport mobile, Open Graph, llms.txt à la racine, robots.txt qui laisse entrer les principaux robots IA.",
      learn_b5_desc: "dateModified ou en-tête Last-Modified, mentions datées dans le corps, année dans le titre quand c’est pertinent.",

      upsell_h2: 'Une page, c’est la démo. <span class="brand-text">Tout votre site, c’est le produit.</span>',
      upsell_p: "Cet outil note une URL à la fois. Oryon note toutes les URL de votre site en continu, suit où vous êtes cité dans ChatGPT, Perplexity, Gemini et Google AI — puis rédige les articles qui vous y font citer.",
      upsell_cta: "Démarrer l’essai gratuit de 3 jours →",
      upsell_fine: "Essai gratuit de 3 jours · 3 articles publiés · 1 audit LLM/GEO approfondi · Annulation en deux clics.",
      stat1_label: "Mentions ChatGPT obtenues pour des clients",
      stat2_label: "Articles bien classés produits",
      stat3_label: "Croissance organique moyenne en 6 mois",

      faq_h2: "Vos questions, nos réponses",
      faq_gA: "Recherche IA & GEO — les bases",
      faq_gB: "Utiliser le score gratuit",
      faq_gC: "SEOryon face aux alternatives",
      faq_gD: "Confiance & fonctionnement",

      faq1_q: "Qu’est-ce que le GEO (generative engine optimization) ?",
      faq1_a: "Le GEO consiste à optimiser pour devenir une source que citent les réponses IA — dans ChatGPT, Perplexity, Gemini, Claude et les AI Overviews de Google — au lieu de seulement se positionner dans les dix liens bleus. De plus en plus de gens interrogent un assistant IA plutôt que de parcourir une page de résultats, et l’assistant cite une poignée de sources. Le GEO, c’est le travail pour en être une : une structure claire, des réponses vraiment utiles, le bon balisage et un accès ouvert aux robots IA.",
      faq2_q: "Comment être cité dans ChatGPT, Perplexity et Google AI ?",
      faq2_a: "Les citations se gagnent comme les positions — en étant la réponse la plus claire et la plus utile à une vraie question — mais l’IA récompense quelques éléments supplémentaires : un contenu bien structuré qu’elle peut extraire (titres, réponses concises, listes, balisage FAQ), une expertise et des signaux de confiance démontrés (auteur nommé, citations vers des sources d’autorité), et un site qui laisse entrer les robots IA. Le score gratuit de cette page vous dit exactement où vous en êtes sur les 27 signaux qui déterminent votre probabilité d’être cité.",
      faq3_q: "En quoi se classer dans les réponses IA diffère-t-il du classement Google ?",
      faq3_a: "Google classe des pages ; les réponses IA citent des sources au sein d’une réponse générée. Les fondamentaux se recoupent — qualité, structure, autorité — mais l’IA récompense le contenu qui répond directement à la question dès les premières phrases, utilise une structure extractible (listes, définitions, Q/R) et expose un balisage lisible par les machines. Une page peut bien se positionner de façon classique et perdre des citations IA si elle enfouit la réponse. SEOryon optimise pour les deux.",
      faq4_q: "Pourquoi les AI Overviews changent-ils le SEO ?",
      faq4_a: "Parce que l’assistant donne la réponse directement sur la page de résultats. Si vous n’êtes pas une des sources citées, le clic n’a jamais lieu. Le SEO ne meurt pas pour autant — l’enjeu se déplace. Le nouvel enjeu, c’est d’être la source citable. Le travail pour y arriver est structurel (réponses claires, schema, llms.txt, accès robots) — sur la même qualité de contenu que vous viseriez de toute façon.",

      faq5_q: "Que signifient les 5 catégories et les 27 signaux ?",
      faq5_a: "Le score est normalisé sur 100 et réparti sur cinq catégories pondérées selon leur influence sur les citations IA : schema & structure (30 pts, 8 signaux), format du contenu (25 pts, 5 signaux), autorité (20 pts, 5 signaux), crawlabilité (15 pts, 6 signaux), fraîcheur (10 pts, 3 signaux). Chaque signal renvoie réussite / partiel / échec avec un correctif précis indiquant exactement quoi changer.",
      faq6_q: "Pourquoi coller une URL d’article et pas la page d’accueil ?",
      faq6_a: "Les pages d’accueil sont des hubs de navigation ; les assistants IA les citent rarement. Ils citent des pages profondes et spécifiques qui répondent à une question précise — articles, guides, FAQ, comparatifs. Analysez la page la plus profonde et utile que vous ayez. Le résultat en dira bien plus sur la citabilité réelle de votre contenu.",
      faq7_q: "Le score est-il vraiment gratuit ? Sans inscription, sans appel à un LLM ?",
      faq7_a: "Oui. L’outil est un parseur HTML déterministe — il récupère votre URL, lit le balisage et exécute 27 vérifications fondées sur des règles. Aucun appel à un LLM, aucune clé d’API, aucun compte, aucun rate-limit. Le code est open source sous MIT, et vous pouvez l’auto-héberger ou l’utiliser en terminal avec pip install oryon-score.",
      faq8_q: "Quelle différence entre le score gratuit et la plateforme SEOryon ?",
      faq8_a: "Le score gratuit audite une URL à la fois, à la demande. SEOryon (la plateforme payante) le fait en continu sur chaque URL de votre site, suit où vous êtes réellement cité dans ChatGPT, Perplexity, Gemini, Google AI et Claude — et rédige les articles qui vous rendent citable au départ. Le score répond à : « cette page est-elle citable ? ». SEOryon répond à : « que dois-je publier ensuite, et où suis-je en train de gagner ? ».",

      faq9_q: "En quoi SEOryon diffère-t-il d’un outil de mots-clés ou d’un rédacteur IA ?",
      faq9_a: "Les outils de mots-clés s’arrêtent à une liste : ils vous disent ce que les gens recherchent, puis vous laissent le plus dur — décider de ce qui mérite vraiment d’être écrit, et l’écrire. Les rédacteurs IA font l’inverse : ils produisent du texte vite, mais sans ancrage dans des données de recherche réelles, d’où des articles génériques qui ne se positionnent pas. SEOryon referme la boucle. Un seul agent analyse de vrais signaux de recherche — SERP en direct, autres questions posées, difficulté des mots-clés, écarts avec les concurrents, tendances —, décide quels sujets feront réellement bouger votre trafic et pourquoi, puis rédige chaque article à partir de ces données et en vérifie les faits. Vous obtenez la recherche d’un outil de mots-clés et la production d’un rédacteur, reliées entre elles, au lieu de payer les deux et de tout assembler vous-même.",
      faq10_q: "Ai-je encore besoin d’Ahrefs ou de Semrush ?",
      faq10_a: "Pour la plupart des équipes, non. SEOryon suit déjà ce que ces outils font remonter — vos positions, vos concurrents, vos backlinks et la santé technique de votre site — mais au lieu de s’arrêter à un tableau de bord sur lequel vous devez encore agir, il agit : il transforme ces signaux en contenu publié qui se positionne. Ahrefs et Semrush sont des bibliothèques de référence ; SEOryon, c’est l’équipe qui lit la bibliothèque et fait le travail. Gardez-les si vous aimez les données, mais vous n’en aurez pas besoin pour grandir.",
      faq11_q: "Pourquoi SEOryon plutôt qu’une agence ou du manuel ?",
      faq11_a: "Une agence coûte cher, avance lentement, et vous ne savez jamais vraiment ce que vous payez ; faire son SEO soi-même engloutit des heures chaque semaine en recherche, rédaction et suivi. SEOryon fait tourner toute cette boucle, de la recherche à la publication, en continu, pour une fraction d’un forfait d’agence — et contrairement à une agence, rien n’est une boîte noire : vous voyez chaque recommandation et validez chaque article. Vous obtenez une production à l’échelle d’une agence, avec un contrôle total et sans la corvée.",

      faq12_q: "Le contenu rédigé par IA est-il pénalisé par Google ?",
      faq12_a: "Non — Google récompense le contenu utile, quelle que soit la façon dont il a été créé, et pénalise le spam. SEOryon rédige de vrais articles fondés sur des faits, que vous relisez avant publication, pas du remplissage produit à la chaîne. Le score de cette page est lui-même fondé sur des règles : il ne produit ni ne réécrit votre contenu, il mesure simplement si votre page existante est structurée pour être citée.",
      faq13_q: "Respectez-vous les règles de Google ?",
      faq13_a: "Toujours. Aucune technique black hat, aucun réseau d’échange de liens, aucun contenu généré sans valeur — uniquement les fondamentaux d’un bon SEO, car c’est la seule croissance qui dure. Les recommandations du score reprennent les mêmes fondamentaux que ceux décrits par les propres conseils de Google sur la recherche IA.",
      faq14_q: "SEOryon modifie-t-il mon site ?",
      faq14_a: "Non. SEOryon vous montre les données et rédige le contenu ; c’est vous qui publiez et qui gardez le contrôle total de votre propre site. Nous ne modifions jamais votre site à votre place. Le score gratuit est en lecture seule — il récupère l’URL publique et lit le HTML, rien de plus.",
      faq15_q: "Qui décide de ce qui est publié ?",
      faq15_a: "Vous. En semi-pilote, vous validez chaque contenu en un clic ; en pilote complet, SEOryon publie selon vos règles. Dans tous les cas, rien ne part en ligne sans votre accord.",
      faq16_q: "Qu’est-ce qui est inclus dans l’essai gratuit de 3 jours ?",
      faq16_a: "Un essai gratuit de 3 jours de la plateforme SEOryon complète : 3 articles publiés rédigés pour vous et 1 audit LLM/GEO approfondi, avec un accès complet. Annulable en deux clics — sans gymnastique de carte bancaire, sans piège de reconduction automatique.",

      footer_privacy: "Confidentialité",
      footer_github: "Open source sur GitHub",
      footer_note: "Un audit GEO gratuit par SEOryon — votre moteur de croissance organique. Inspiré de l’approche par signaux structurés de citation-intelligence, par AutomateLab. Cet outil est une œuvre originale sous licence MIT.",

      r_scoring: "récupération · analyse · scoring",
      r_top_fixes: "Correctifs prioritaires",
      r_top_fixes_sub: "(par impact)",
      r_whats_working: "Ce qui fonctionne déjà",
      r_grade: "Note",
      r_scoring_btn: "Analyse…",
    },
  };

  const SUPPORTED = ["en", "de", "fr"];
  const STORAGE_KEY = "seoryon_lang";
  let currentLang = "en";

  const pickInitialLang = () => {
    try {
      const q = new URLSearchParams(window.location.search).get("lang");
      if (q && SUPPORTED.includes(q.toLowerCase())) return q.toLowerCase();
    } catch (_) { /* ignore */ }
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && SUPPORTED.includes(saved)) return saved;
    } catch (_) { /* localStorage may be blocked */ }
    const nav = (navigator.language || "en").slice(0, 2).toLowerCase();
    return SUPPORTED.includes(nav) ? nav : "en";
  };

  const applyLang = (lang) => {
    currentLang = SUPPORTED.includes(lang) ? lang : "en";
    const dict = I18N[currentLang] || I18N.en;

    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const v = dict[el.getAttribute("data-i18n")];
      if (v != null) el.textContent = v;
    });
    document.querySelectorAll("[data-i18n-html]").forEach((el) => {
      const v = dict[el.getAttribute("data-i18n-html")];
      if (v != null) el.innerHTML = v;
    });

    if (dict.meta_title) document.title = dict.meta_title;
    const md = document.querySelector('meta[name="description"]');
    if (md && dict.meta_desc) md.setAttribute("content", dict.meta_desc);
    document.documentElement.setAttribute("lang", currentLang);

    document.querySelectorAll(".lang-btn").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-lang") === currentLang);
    });

    try { localStorage.setItem(STORAGE_KEY, currentLang); } catch (_) { /* ignore */ }
  };

  // FAQPage structured data — built once from the EN source dict so Google/LLMs
  // can parse the Q&As. Static HTML mirrors the EN answers for crawlers.
  const injectFaqLd = () => {
    const en = I18N.en;
    const qa = [];
    for (let i = 1; i <= 16; i++) {
      const q = en["faq" + i + "_q"], a = en["faq" + i + "_a"];
      if (q && a) qa.push({
        "@type": "Question",
        name: q,
        acceptedAnswer: { "@type": "Answer", text: a },
      });
    }
    const ld = {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      mainEntity: qa,
    };
    const s = document.createElement("script");
    s.type = "application/ld+json";
    s.textContent = JSON.stringify(ld);
    document.head.appendChild(s);
  };

  // ----- SCORING UI -----
  const form = document.getElementById("scoreForm");
  const input = document.getElementById("urlInput");
  const btn = document.getElementById("scoreBtn");
  const out = document.getElementById("result");

  const fmtBucket = (key) =>
    key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  const escapeHtml = (s) => String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

  const renderError = (msg) => {
    out.classList.remove("hidden");
    out.innerHTML = `<div class="error-card">${escapeHtml(msg)}</div>`;
  };

  const renderResult = (r) => {
    const dict = I18N[currentLang] || I18N.en;
    const tone = r.score >= 70 ? "" : r.score >= 50 ? "warn" : "danger";
    const buckets = Object.entries(r.bucket_scores)
      .map(([k, v]) => `
        <div class="bucket-row">
          <div class="bucket-name">${fmtBucket(k)}</div>
          <div class="bucket-bar"><div class="bucket-fill" style="width:${v.percent}%"></div></div>
          <div class="bucket-pts">${v.earned}/${v.max}</div>
        </div>`).join("");

    const failed = r.signals.filter((s) => !s.passed);
    const passed = r.signals.filter((s) => s.passed);

    const fixHtml = failed
      .slice()
      .sort((a, b) => b.weight - a.weight)
      .slice(0, 8)
      .map((s) => `
        <div class="fix-item">
          <div class="icon">✗</div>
          <div>
            <div class="name">${escapeHtml(s.name)}</div>
            <div class="desc">${escapeHtml(s.detail)}</div>
            ${s.fix ? `<div class="desc fix" style="margin-top:6px;">→ ${escapeHtml(s.fix)}</div>` : ""}
          </div>
        </div>`).join("");

    const passHtml = passed
      .slice(0, 6)
      .map((s) => `
        <div class="fix-item">
          <div class="icon ok">✓</div>
          <div>
            <div class="name">${escapeHtml(s.name)}</div>
            <div class="desc">${escapeHtml(s.detail)}</div>
          </div>
        </div>`).join("");

    const notesHtml = (r.notes && r.notes.length)
      ? `<div class="notice">${r.notes.map(n => `<div>${escapeHtml(n)}</div>`).join("")}</div>`
      : "";

    out.classList.remove("hidden");
    out.innerHTML = `
      <div class="score-card">
        <div class="score-header">
          <div>
            <div class="url-label">${escapeHtml(r.url)}</div>
            ${r.page_title ? `<div class="page-title">${escapeHtml(r.page_title)}</div>` : ""}
          </div>
          <div style="text-align:right;">
            <div class="score-big ${tone}">${r.score}<span style="font-size:36px;opacity:0.6;">/100</span></div>
            <div class="grade-pill">${escapeHtml(dict.r_grade)} ${escapeHtml(r.grade)}</div>
          </div>
        </div>
        ${notesHtml}
        <div class="buckets">${buckets}</div>
      </div>

      ${fixHtml ? `<div class="section-title">${escapeHtml(dict.r_top_fixes)} <span style="font-size:14px;font-weight:500;color:var(--ink-muted);">${escapeHtml(dict.r_top_fixes_sub)}</span></div><div class="fix-list">${fixHtml}</div>` : ""}
      ${passHtml ? `<div class="section-title">${escapeHtml(dict.r_whats_working)}</div><div class="fix-list">${passHtml}</div>` : ""}
    `;
    out.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const run = async (url) => {
    const dict = I18N[currentLang] || I18N.en;
    btn.disabled = true;
    btn.textContent = dict.r_scoring_btn;
    out.classList.remove("hidden");
    out.innerHTML = `<div class="score-card" style="text-align:center;padding:48px;"><div class="score-big">…</div><div style="margin-top:12px;color:var(--ink-muted);font-family:'Geist Mono',monospace;font-size:13px;">${escapeHtml(dict.r_scoring)}</div></div>`;
    try {
      const resp = await fetch(`/api/score?url=${encodeURIComponent(url)}`);
      const data = await resp.json();
      if (!resp.ok || data.error) {
        renderError(data.error || `HTTP ${resp.status}`);
      } else {
        renderResult(data);
      }
    } catch (e) {
      renderError(String(e));
    } finally {
      btn.disabled = false;
      btn.textContent = dict.score_btn;
    }
  };

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const v = input.value.trim();
      if (!v) return;
      run(v);
    });
  }

  // Language switcher
  document.querySelectorAll(".lang-btn").forEach((b) => {
    b.addEventListener("click", () => applyLang(b.getAttribute("data-lang")));
  });

  // Boot
  injectFaqLd();
  applyLang(pickInitialLang());

  // Allow URL prefill via ?url=
  const params = new URLSearchParams(window.location.search);
  const prefill = params.get("url");
  if (prefill && input) {
    input.value = prefill;
    run(prefill);
  }
})();
